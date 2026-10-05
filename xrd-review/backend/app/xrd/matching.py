"""候选物相匹配：匈牙利算法一对一配峰 + 可解释的评分与证据列表。

原则（对应课程要求）：
- 不按"命中最多"给唯一结论 —— 返回全部候选及各自证据；
- 每个候选都列出：命中的峰、参考有而样品未见的峰、样品中该候选解释不了的峰；
- 评分透明：覆盖率(按参考强度加权) 与 样品可解释分数 分别报告，
  综合分 = 0.5*coverage + 0.5*explained，仅为排序参考，不构成鉴定结论；
- 超出样品测量范围的参考峰不计入"缺失"（本来就观测不到）；
- 匹配容差为显式参数；未给时自动取 max(0.05°, 0.5*仪器FWHM)。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import linear_sum_assignment

from .peaks import PeakList
from .units import d_to_two_theta

MIN_AUTO_TOLERANCE_DEG = 0.05
DEFAULT_TOLERANCE_DEG = 0.15


@dataclass
class RefPeak:
    d_angstrom: float
    intensity_rel: float          # 参考相对强度（0-100）
    two_theta_deg: float = 0.0    # 按请求波长换算后填入


@dataclass
class MatchedPair:
    sample_two_theta: float
    ref_two_theta: float
    delta_two_theta: float
    sample_intensity: float
    ref_intensity: float


@dataclass
class CandidateReport:
    reference_id: int
    name: str
    formula: str
    score: float
    coverage: float               # 命中参考峰强度 / 可观测参考峰总强度
    explained_fraction: float     # 被解释的样品峰强度 / 样品峰总强度
    n_matched: int
    matched: list[MatchedPair] = field(default_factory=list)
    missing_ref_peaks: list[RefPeak] = field(default_factory=list)      # 参考有、样品未见
    unexplained_sample_peaks: list[dict] = field(default_factory=list)  # 样品有、本候选解释不了
    mean_abs_delta: float | None = None
    tolerance_deg: float = 0.0


def auto_tolerance(instrument_fwhm_deg: float) -> float:
    return max(MIN_AUTO_TOLERANCE_DEG, 0.5 * instrument_fwhm_deg)


def match_one(
    sample: PeakList,
    ref_peaks: list[RefPeak],
    reference_id: int,
    name: str,
    formula: str,
    wavelength_angstrom: float,
    sample_range_deg: tuple[float, float],
    detection_threshold_rel: float,
    tolerance_deg: float,
) -> CandidateReport:
    """对单个参考条目做匹配并生成证据报告。"""
    # 参考峰换算到 2θ，并只保留落在样品测量范围内、且强度高于检测阈值的峰
    observable: list[RefPeak] = []
    out_of_range = 0
    lo, hi = sample_range_deg
    for rp in ref_peaks:
        tt = float(d_to_two_theta(rp.d_angstrom, wavelength_angstrom))
        if np.isnan(tt):
            continue
        rp.two_theta_deg = tt
        if lo <= tt <= hi:
            if rp.intensity_rel >= detection_threshold_rel:
                observable.append(rp)
        else:
            out_of_range += 1

    s_pos = sample.positions
    s_int = np.array([p.intensity_norm for p in sample.peaks]) if sample.peaks else np.zeros(0)

    matched: list[MatchedPair] = []
    used_ref: set[int] = set()
    used_sample: set[int] = set()

    if len(observable) and len(s_pos):
        r_pos = np.array([rp.two_theta_deg for rp in observable])
        diff = np.abs(s_pos[:, None] - r_pos[None, :])
        big = 1.0e6
        cost = np.where(diff <= tolerance_deg, diff, big)
        rows, cols = linear_sum_assignment(cost)
        for r, c in zip(rows, cols):
            if cost[r, c] >= big:
                continue
            used_sample.add(int(r))
            used_ref.add(int(c))
            matched.append(MatchedPair(
                sample_two_theta=float(s_pos[r]),
                ref_two_theta=float(r_pos[c]),
                delta_two_theta=float(s_pos[r] - r_pos[c]),
                sample_intensity=float(s_int[r]),
                ref_intensity=float(observable[c].intensity_rel),
            ))

    missing = [rp for i, rp in enumerate(observable) if i not in used_ref]
    unexplained = [
        {"two_theta_deg": float(s_pos[i]), "intensity_norm": float(s_int[i])}
        for i in range(len(s_pos)) if i not in used_sample
    ]

    ref_int_total = sum(rp.intensity_rel for rp in observable)
    ref_int_hit = sum(m.ref_intensity for m in matched)
    coverage = (ref_int_hit / ref_int_total) if ref_int_total > 0 else 0.0

    s_int_total = float(np.sum(s_int)) if len(s_int) else 0.0
    s_int_explained = sum(m.sample_intensity for m in matched)
    explained = (s_int_explained / s_int_total) if s_int_total > 0 else 0.0

    score = 0.5 * coverage + 0.5 * explained
    mean_abs = float(np.mean([abs(m.delta_two_theta) for m in matched])) if matched else None

    return CandidateReport(
        reference_id=reference_id, name=name, formula=formula,
        score=round(score, 4), coverage=round(coverage, 4),
        explained_fraction=round(explained, 4),
        n_matched=len(matched), matched=matched,
        missing_ref_peaks=missing, unexplained_sample_peaks=unexplained,
        mean_abs_delta=mean_abs, tolerance_deg=tolerance_deg,
    )


def rank_candidates(reports: list[CandidateReport]) -> list[CandidateReport]:
    """按综合分排序返回全部候选 —— 不裁剪、不替用户下唯一结论。"""
    return sorted(reports, key=lambda r: r.score, reverse=True)
