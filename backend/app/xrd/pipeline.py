"""分析流水线：单位换算 -> 零点校正 -> 去背景 -> 峰检测 -> 全候选对照。

强度归一仅用于展示（归一化谱单独返回），**绝不参与峰检测与峰位置计算**。
"""

from __future__ import annotations

import numpy as np

from .background import subtract_background
from .matching import match_all
from .peaks import detect_peaks
from .units import apply_zero_shift, describe_convention, to_two_theta_deg


def _normalize(y: np.ndarray) -> np.ndarray:
    ymax = float(np.max(y)) if y.size else 0.0
    if ymax <= 0:
        return y.astype(float)
    return y.astype(float) / ymax


def run_analysis(
    two_theta,
    intensity,
    references: list[dict],
    reference_peaks: dict[str, list[dict]],
    *,
    wavelength: float,
    wavelength_unit: str,
    angle_unit: str = "2theta_deg",
    zero_shift: float = 0.0,
    bg_window: int = 40,
    bg_iterations: int = 24,
    bg_smoothing: int = 3,
    prominence_sigma: float = 3.0,
    min_separation_deg: float = 0.05,
    min_fwhm_deg: float = 0.03,
    max_fwhm_deg: float = 3.0,
    instrument_fwhm_deg: float = 0.1,
    uncertainty_fraction: float = 0.1,
    tolerance_deg: float = 0.15,
    minimum_hits: int = 2,
    shift_scan_max: float = 2.0,
    shift_scan_step: float = 0.02,
) -> dict:
    x_raw = to_two_theta_deg(two_theta, angle_unit)
    y_raw = np.asarray(intensity, dtype=float)
    if x_raw.shape != y_raw.shape or x_raw.size < 5:
        raise ValueError("角度与强度数组长度不一致或点数过少")

    # 零点校正只作用于角轴；强度原样不动
    x = apply_zero_shift(x_raw, zero_shift)

    bg, net = subtract_background(
        y_raw, window=bg_window, iterations=bg_iterations, smoothing=bg_smoothing
    )

    peak_result = detect_peaks(
        x,
        y_raw,
        net,
        prominence_sigma=prominence_sigma,
        min_separation_deg=min_separation_deg,
        min_fwhm_deg=min_fwhm_deg,
        max_fwhm_deg=max_fwhm_deg,
        instrument_fwhm_deg=instrument_fwhm_deg,
        uncertainty_fraction=uncertainty_fraction,
    )

    matching = match_all(
        peak_result["peaks"],
        references,
        reference_peaks,
        x_range=(float(x.min()), float(x.max())),
        tolerance_deg=tolerance_deg,
        minimum_hits=minimum_hits,
        shift_scan_max=shift_scan_max,
        shift_scan_step=shift_scan_step,
    )

    # 展示用归一化谱（原始与去背景并列；不回写到检测/匹配流程）
    raw_norm = _normalize(y_raw)
    net_norm = _normalize(net)

    # 全样本未解释峰：取通过候选（>=minimum_hits）解释不了的峰并集之外的峰
    explained = set()
    for cand in matching["candidates"]:
        if cand["passes_minimum_hits"]:
            for p in cand["matched"]:
                explained.add(p["sample_two_theta"])
    unexplained = [
        p
        for p in peak_result["peaks"]
        if p["two_theta"] not in explained
    ]

    return {
        "convention": describe_convention(
            wavelength, wavelength_unit, angle_unit, zero_shift
        ),
        "processing": {
            "background_method": "SNIP",
            "background_params": {
                "window": bg_window,
                "iterations": bg_iterations,
                "smoothing": bg_smoothing,
            },
            "normalization": "原始谱与去背景谱分别按各自最大值归一，仅用于展示；峰检测/匹配使用未归一化数据，峰位置不受归一化影响",
        },
        "curves": {
            "two_theta_corrected": np.round(x, 4).tolist(),
            "raw_intensity": np.round(y_raw, 4).tolist(),
            "background": np.round(bg, 4).tolist(),
            "net_intensity": np.round(net, 4).tolist(),
            "raw_normalized": np.round(raw_norm, 5).tolist(),
            "net_normalized": np.round(net_norm, 5).tolist(),
        },
        "peaks": peak_result,
        "matching": matching,
        "unexplained_overall": unexplained,
        "disclaimer": (
            "本结果是教学用离线复核：候选仅表示在显式波长、容差与展宽参数下的"
            "角度相符程度，不构成自动物相鉴定。最终物相判断须由人工结合全部依据完成。"
        ),
    }
