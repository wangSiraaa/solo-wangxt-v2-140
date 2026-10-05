"""峰检测：SciPy find_peaks + 抛物线亚点修正，参数全部显式。

检测在**去背景谱**上进行，但峰位置在（已做零点校正的）原始角轴上读取——
任何强度归一/去背景操作都不会改变峰位置。

显式参数
--------
prominence_sigma : 检测阈值，单位为去背景谱噪声标准差的倍数（默认 3.0）。
                  噪声由谱的稳健估计（中位绝对偏差 MAD）给出，
                  阈值 = prominence_sigma * 1.4826 * MAD(net)。
min_separation_deg : 两峰最小角间距（°），小于该值的弱峰被抑制。
max_fwhm_deg : 峰宽上限（°）。宽于该值的峰（例如无定形鼓包）被标记并剔除，
               同时在 rejected_broad 中返回，保证宽峰案例可被显式检查。
min_fwhm_deg : 峰宽下限（°），防止把单点噪声当峰。
instrument_fwhm_deg : 仪器展宽（°，显式参数）。仅用于从实测 FWHM 反卷积
                      估计样品本征宽化 β = sqrt(B² - b_inst²)；
                      不参与峰检测，也不改变峰位。
uncertainty_fraction : 峰位不确定度 = uncertainty_fraction * 实测 FWHM（默认 0.1）。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict

import numpy as np
from scipy.signal import find_peaks, peak_widths


def _mad_noise(y: np.ndarray) -> float:
    med = np.median(y)
    mad = np.median(np.abs(y - med))
    return 1.4826 * mad if mad > 0 else float(np.std(y))


def _parabolic_refinement(x: np.ndarray, y: np.ndarray, idx: int) -> tuple[float, float]:
    """三点抛物线插值，返回（亚点偏移, 插值后的峰高）。偏移单位为采样点。"""
    if idx <= 0 or idx >= y.size - 1:
        return 0.0, float(y[idx])
    y0, y1, y2 = y[idx - 1], y[idx], y[idx + 1]
    denom = y0 - 2.0 * y1 + y2
    if denom == 0:
        return 0.0, float(y1)
    delta = 0.5 * (y0 - y2) / denom
    delta = float(np.clip(delta, -1.0, 1.0))
    h = y1 - 0.25 * (y0 - y2) * delta
    return delta, float(h)


@dataclass
class Peak:
    two_theta: float
    intensity_net: float
    intensity_raw: float
    fwhm_deg: float
    intrinsic_fwhm_deg: float          # 去掉仪器展宽后的本征宽化；负数表示不可解析
    broadening_resolved: bool
    position_uncertainty_deg: float
    hkl_hint: str | None = None


def detect_peaks(
    two_theta,
    raw,
    net,
    *,
    prominence_sigma: float = 3.0,
    min_separation_deg: float = 0.05,
    min_fwhm_deg: float = 0.03,
    max_fwhm_deg: float = 3.0,
    instrument_fwhm_deg: float = 0.1,
    uncertainty_fraction: float = 0.1,
) -> dict:
    """在去背景谱上检测峰，返回 {peaks: [Peak...], rejected_broad: [...], noise_sigma, threshold}。

    宽峰（FWHM > max_fwhm_deg）不静默丢弃：放入 rejected_broad 单独报告。
    """
    x = np.asarray(two_theta, dtype=float)
    y_raw = np.asarray(raw, dtype=float)
    y = np.asarray(net, dtype=float)
    if x.size < 5 or not np.all(np.diff(x) > 0):
        raise ValueError("角轴必须严格单调递增且至少含 5 个点")

    dx = float(np.median(np.diff(x)))
    noise = float(_mad_noise(y))
    threshold = float(prominence_sigma * noise)

    distance_pts = max(1, int(round(min_separation_deg / dx)))
    min_width = max(1, int(math.floor(min_fwhm_deg / dx)))
    max_width = max(min_width + 1, int(math.ceil(max_fwhm_deg / dx)))

    idx, props = find_peaks(
        y,
        prominence=max(threshold, 1e-12),
        distance=distance_pts,
        # 只设宽度下限；上限不在 SciPy 层静默丢弃，而是检出后显式分类到 rejected_broad
        width=(min_width, None),
        rel_height=0.5,
    )

    widths_pts, _, _, _ = peak_widths(y, idx, rel_height=0.5) if idx.size else (
        np.array([]), np.array([]), np.array([]), np.array([])
    )

    peaks: list[Peak] = []
    rejected_broad = []
    rejected_narrow = 0
    for i, ip in enumerate(idx):
        fwhm_pts = float(widths_pts[i]) if i < len(widths_pts) else 1.0
        fwhm_deg = fwhm_pts * dx
        delta, h_interp = _parabolic_refinement(x, y, int(ip))
        pos = float(x[int(ip)] + delta * dx)

        if fwhm_deg < min_fwhm_deg:
            # width 下限按采样点取整，这里用角度制再判一次，剔除单点噪声尖峰
            rejected_narrow += 1
            continue
        if fwhm_deg > max_fwhm_deg:
            rejected_broad.append(
                {
                    "two_theta": round(pos, 4),
                    "fwhm_deg": round(fwhm_deg, 3),
                    "intensity_net": round(float(y[int(ip)]), 4),
                    "reason": f"FWHM={fwhm_deg:.2f}° 超过显式上限 {max_fwhm_deg:.2f}°，疑似宽化/无定形峰",
                }
            )
            continue

        b_inst = float(instrument_fwhm_deg)
        intrinsic_sq = fwhm_deg * fwhm_deg - b_inst * b_inst
        resolved = intrinsic_sq > 0
        intrinsic = math.sqrt(intrinsic_sq) if resolved else float("nan")

        peaks.append(
            Peak(
                two_theta=round(pos, 4),
                intensity_net=round(h_interp, 4),
                intensity_raw=round(float(np.interp(pos, x, y_raw)), 4),
                fwhm_deg=round(fwhm_deg, 4),
                intrinsic_fwhm_deg=round(intrinsic, 4) if resolved else None,
                broadening_resolved=resolved,
                position_uncertainty_deg=round(
                    float(uncertainty_fraction) * fwhm_deg, 4
                ),
            )
        )

    return {
        "peaks": [asdict(p) for p in peaks],
        "rejected_broad": rejected_broad,
        "rejected_narrow_count": rejected_narrow,
        "noise_sigma": round(noise, 6),
        "prominence_threshold": round(threshold, 6),
        "params": {
            "prominence_sigma": prominence_sigma,
            "min_separation_deg": min_separation_deg,
            "min_fwhm_deg": min_fwhm_deg,
            "max_fwhm_deg": max_fwhm_deg,
            "instrument_fwhm_deg": instrument_fwhm_deg,
            "uncertainty_fraction": uncertainty_fraction,
        },
    }
