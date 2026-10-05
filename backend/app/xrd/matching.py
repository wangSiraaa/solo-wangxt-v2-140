"""候选匹配：样本峰与参考条目的显式、可复核对照。

设计原则（对应需求）
--------------------
1. 不按"命中最多"给唯一结论：返回**全部**候选，各自带命中、缺失、未解释
   依据与多个独立评分，并按综合分排序；是否成立交给使用者复核。
2. 参考有、样本未见的峰（区分测量范围内外）与样本有、参考解释不了的
   未知峰都必须逐条列出。
3. 匹配只看峰**位置**，且容差与峰位不确定度显式参与；强度仅做一致性评分，
   不用于移动峰位。
4. 零点偏移只使用调用方显式提供的值。另给一个"偏移假设"诊断块
   （suggested_zero_shift 及该偏移下的命中数），但它**不会被自动应用**。
"""

from __future__ import annotations

import numpy as np


def _effective_tol(base_tol: float, sample_uncertainty: float | None) -> float:
    if sample_uncertainty is None:
        return float(base_tol)
    return max(float(base_tol), float(sample_uncertainty))


def _greedy_pair(sample_peaks: list[dict], ref_peaks: list[dict], base_tol: float):
    """贪心最近邻一对一配对。

    每次取全局最小角距的（样本峰，参考峰）对，只要
        |Δ2θ| <= max(base_tol, 该样本峰的位置不确定度)。
    返回 (pairs, unmatched_sample, unmatched_ref)。
    """
    candidates = []
    for i, s in enumerate(sample_peaks):
        for j, r in enumerate(ref_peaks):
            d = abs(s["two_theta"] - r["two_theta"])
            tol = _effective_tol(base_tol, s.get("position_uncertainty_deg"))
            if d <= tol:
                candidates.append((d, tol, i, j))
    candidates.sort(key=lambda t: t[0])

    used_s, used_r = set(), set()
    pairs = []
    for d, tol, i, j in candidates:
        if i in used_s or j in used_r:
            continue
        used_s.add(i)
        used_r.add(j)
        pairs.append(
            {
                "sample_two_theta": sample_peaks[i]["two_theta"],
                "reference_two_theta": ref_peaks[j]["two_theta"],
                "delta": round(sample_peaks[i]["two_theta"] - ref_peaks[j]["two_theta"], 4),
                "abs_delta": round(d, 4),
                "tol_used": round(tol, 4),
                "within_tol": True,
                "sample_fwhm_deg": sample_peaks[i].get("fwhm_deg"),
                "reference_hkl": r.get("hkl"),
                "reference_intensity_rel": r.get("intensity_rel"),
                "sample_intensity_net": sample_peaks[i].get("intensity_net"),
            }
        )
    unmatched_s = [s for i, s in enumerate(sample_peaks) if i not in used_s]
    unmatched_r = [r for j, r in enumerate(ref_peaks) if j not in used_r]
    pairs.sort(key=lambda p: p["sample_two_theta"])
    return pairs, unmatched_s, unmatched_r


def _suggested_shift(pairs: list[dict]) -> float | None:
    """由已配对峰的 Δ2θ 中位数估计系统偏移（仅诊断，不自动应用）。"""
    if not pairs:
        return None
    return round(float(np.median([p["delta"] for p in pairs])), 4)


def _rematch_with_shift(sample_peaks, ref_peaks, base_tol: float, shift: float):
    """在假设额外零点偏移 shift 下重新配对（诊断用）。"""
    shifted = [dict(s, two_theta=s["two_theta"] - shift) for s in sample_peaks]
    pairs, us, ur = _greedy_pair(shifted, ref_peaks, base_tol)
    # 样本角还原为原读数
    for p in pairs:
        p["sample_two_theta"] = round(p["sample_two_theta"] + shift, 4)
    for s in us:
        s["two_theta"] = round(s["two_theta"] + shift, 4)
    return pairs, us, ur


def _score_candidate(
    pairs, unmatched_sample, missing_in_range, ref_peaks, sample_peaks
) -> dict:
    """四个彼此独立的评分维度，均显式给出，避免单一"命中数"结论。"""
    n_ref = len(ref_peaks)
    n_s = len(sample_peaks)
    n_hit = len(pairs)
    hit_rate_ref = n_hit / n_ref if n_ref else 0.0
    hit_rate_sample = n_hit / n_s if n_s else 0.0

    # 位置一致性：1 - 平均|Δ|/平均容差，裁剪到 [0,1]
    if pairs:
        mean_abs = float(np.mean([p["abs_delta"] for p in pairs]))
        mean_tol = float(np.mean([p["tol_used"] for p in pairs]))
        position_score = float(np.clip(1.0 - mean_abs / mean_tol, 0.0, 1.0))
        rms_delta = float(np.sqrt(np.mean([p["delta"] ** 2 for p in pairs])))
    else:
        position_score = 0.0
        rms_delta = None

    # 强度一致性：用归一化（样本命中峰最大值=100）后的相对强度与参考比较
    intensity_score = None
    if pairs:
        smax = max(p["sample_intensity_net"] or 0.0 for p in pairs) or 1.0
        diffs = []
        for p in pairs:
            s_rel = 100.0 * (p["sample_intensity_net"] or 0.0) / smax
            r_rel = p["reference_intensity_rel"] or 0.0
            diffs.append(abs(s_rel - r_rel) / 100.0)
        intensity_score = round(float(1.0 - np.clip(np.mean(diffs), 0.0, 1.0)), 4)

    missing_penalty = len(missing_in_range) / n_ref if n_ref else 0.0
    # 综合分：命中覆盖（参考侧+样本侧各一半）+ 位置一致性 - 缺失惩罚
    overall = (
        0.35 * hit_rate_ref
        + 0.25 * hit_rate_sample
        + 0.30 * position_score
        - 0.10 * missing_penalty
    )
    return {
        "hit_count": n_hit,
        "fraction_reference_explained": round(hit_rate_ref, 4),
        "fraction_sample_explained": round(hit_rate_sample, 4),
        "position_consistency": round(position_score, 4),
        "rms_delta_deg": round(rms_delta, 4) if rms_delta is not None else None,
        "intensity_consistency": intensity_score,
        "missing_in_range_count": len(missing_in_range),
        "overall_score": round(float(np.clip(overall, 0.0, 1.0)), 4),
    }


def match_reference(
    sample_peaks: list[dict],
    reference: dict,
    ref_peaks: list[dict],
    *,
    x_range: tuple[float, float],
    tolerance_deg: float = 0.15,
    minimum_hits: int = 2,
) -> dict:
    """单个候选条目的完整对照结果。"""
    xmin, xmax = x_range
    pairs, unmatched_sample, unmatched_ref = _greedy_pair(
        sample_peaks, ref_peaks, tolerance_deg
    )

    missing_in_range, missing_outside = [], []
    for r in unmatched_ref:
        row = {
            "reference_two_theta": r["two_theta"],
            "reference_hkl": r.get("hkl"),
            "reference_intensity_rel": r.get("intensity_rel"),
        }
        if xmin <= r["two_theta"] <= xmax:
            missing_in_range.append(row)
        else:
            missing_outside.append(row)

    unknown_peaks = [
        {
            "sample_two_theta": s["two_theta"],
            "sample_fwhm_deg": s.get("fwhm_deg"),
            "sample_intensity_net": s.get("intensity_net"),
            "position_uncertainty_deg": s.get("position_uncertainty_deg"),
        }
        for s in unmatched_sample
    ]

    scores = _score_candidate(
        pairs, unmatched_sample, missing_in_range, ref_peaks, sample_peaks
    )
    shift = _suggested_shift(pairs)

    shift_diagnostic = None
    if shift is not None and abs(shift) > tolerance_deg:
        spairs, _, _ = _rematch_with_shift(
            sample_peaks, ref_peaks, tolerance_deg, shift
        )
        shift_diagnostic = {
            "suggested_zero_shift_deg": shift,
            "hits_without_shift": len(pairs),
            "hits_if_shift_applied": len(spairs),
            "note": "仅为系统偏移诊断；不会自动应用。请在零点偏移参数中显式填入后重算。",
        }

    return {
        "reference_code": reference["code"],
        "reference_name": reference["name"],
        "reference_wavelength_angstrom": reference["wavelength_angstrom"],
        "provenance": reference.get("provenance"),
        "matched": pairs,
        "missing_in_range": missing_in_range,
        "missing_outside_measured_range": missing_outside,
        "unknown_sample_peaks": unknown_peaks,
        "scores": scores,
        "passes_minimum_hits": len(pairs) >= minimum_hits,
        "shift_diagnostic": shift_diagnostic,
        "disclaimer": "命中关系仅表示在显式容差内角距相符，不构成物相鉴定结论。",
    }


def match_all(
    sample_peaks: list[dict],
    references: list[dict],
    reference_peaks: dict[str, list[dict]],
    *,
    x_range: tuple[float, float],
    tolerance_deg: float = 0.15,
    minimum_hits: int = 2,
    shift_scan_max: float = 2.0,
    shift_scan_step: float = 0.02,
) -> dict:
    """对全部参考条目做对照，排序但不剔除任何候选。

    另做一次**独立的系统偏移扫描**：在 [-shift_scan_max, +shift_scan_max] 内
    寻找"命中数最多"的偏移假设。它只是诊断提示，绝不自动改变峰位或结论。
    """
    candidates = []
    for ref in references:
        candidates.append(
            match_reference(
                sample_peaks,
                ref,
                reference_peaks[ref["code"]],
                x_range=x_range,
                tolerance_deg=tolerance_deg,
                minimum_hits=minimum_hits,
            )
        )
    candidates.sort(
        key=lambda c: (c["scores"]["overall_score"], c["scores"]["hit_count"]),
        reverse=True,
    )

    shift_scan = _shift_scan(
        sample_peaks,
        references,
        reference_peaks,
        tolerance_deg=tolerance_deg,
        scan_max=shift_scan_max,
        step=shift_scan_step,
    )

    passing = [c for c in candidates if c["passes_minimum_hits"]]
    return {
        "candidates": candidates,
        "shift_scan": shift_scan,
        "summary": {
            "n_candidates_evaluated": len(candidates),
            "n_candidates_passing_min_hits": len(passing),
            "ordered_by": "overall_score（综合分=覆盖度+位置一致性-缺失惩罚），不是命中数",
            "no_unique_conclusion": (
                "本工具不输出唯一物相结论。排名靠前仅代表角度相符程度，"
                "请结合缺失峰、未知峰、强度与化学背景人工复核。"
            ),
        },
    }


def _shift_scan(
    sample_peaks: list[dict],
    references: list[dict],
    reference_peaks: dict[str, list[dict]],
    *,
    tolerance_deg: float,
    scan_max: float,
    step: float,
) -> dict:
    """对每个参考在偏移网格上数命中数，报告最有利的偏移假设（仅诊断）。"""
    if not sample_peaks:
        return {"enabled": False, "reason": "无样本峰，跳过偏移扫描"}
    shifts = np.round(np.arange(-scan_max, scan_max + 0.5 * step, step), 4)
    rows = []
    for ref in references:
        rpeaks = reference_peaks[ref["code"]]
        ref_pos = np.array([r["two_theta"] for r in rpeaks])
        best = {"hits": 0, "shift": 0.0}
        baseline = 0
        for sh in shifts:
            moved = np.array([s["two_theta"] for s in sample_peaks]) - sh
            # 一对一贪心计数
            hits = 0
            used_r = set()
            order = np.argsort(moved)
            for i in order:
                d = np.abs(ref_pos - moved[i])
                j = int(np.argmin(d))
                tol = max(
                    tolerance_deg,
                    sample_peaks[int(i)].get("position_uncertainty_deg") or 0.0,
                )
                if d[j] <= tol and j not in used_r:
                    used_r.add(j)
                    hits += 1
            if abs(float(sh)) < 0.5 * step:
                baseline = hits
            if hits > best["hits"]:
                best = {"hits": hits, "shift": float(sh)}
        rows.append(
            {
                "reference_code": ref["code"],
                "hits_at_zero_shift": baseline,
                "best_hits_under_scan": best["hits"],
                "suggested_zero_shift_deg": best["shift"] if best["hits"] > baseline else 0.0,
            }
        )
    rows.sort(key=lambda r: (r["best_hits_under_scan"], r["hits_at_zero_shift"]), reverse=True)
    return {
        "enabled": True,
        "scan_range_deg": [-scan_max, scan_max],
        "scan_step_deg": step,
        "per_reference": rows,
        "note": (
            "偏移扫描仅用于发现可能的系统零点误差；即使某偏移显著提高命中数，"
            "也不会自动应用。请确认仪器/制样原因后，在 zero_shift 参数中显式填入再重算。"
        ),
    }
