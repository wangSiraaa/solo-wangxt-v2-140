"""峰检测：Savitzky-Golay 平滑辅助检测 + 噪声自适应阈值 + 抛物线亚步长细化。

显式参数：
- detection_threshold_rel：相对去背景后最大强度的百分比（默认 1%）；
- noise_sigma_factor：噪声下限倍数，有效阈值 = max(相对阈值, k·σ_noise)，
  σ_noise 由一阶差分的中位绝对偏差(MAD)估计；
- instrument_fwhm_deg：仪器展宽（度 2θ），决定最小峰宽与平滑窗。

平滑只用于"找"峰；峰位与峰高始终在未平滑的去背景谱上确定。
归一化只缩放强度（最高=100），绝不动峰位。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.signal import find_peaks, peak_widths, savgol_filter

DEFAULT_THRESHOLD_REL = 1.0      # % of max background-subtracted intensity
DEFAULT_NOISE_SIGMA_FACTOR = 5.0


@dataclass
class Peak:
    two_theta_deg: float          # 已做零点校正后的位置
    intensity_norm: float         # 归一强度（最高=100）
    height_abs: float             # 去背景后的绝对高度
    fwhm_deg: float               # 半高宽（度）
    d_angstrom: float = 0.0       # 由波长换算，仅作展示


@dataclass
class PeakList:
    peaks: list[Peak] = field(default_factory=list)
    noise_sigma: float = 0.0
    threshold_abs: float = 0.0

    @property
    def positions(self) -> np.ndarray:
        return np.array([p.two_theta_deg for p in self.peaks])


def estimate_noise_sigma(y: np.ndarray) -> float:
    """由一阶差分的 MAD 估计白噪声标准差（对缓变背景与峰不敏感）。"""
    d = np.diff(np.asarray(y, dtype=float))
    if len(d) == 0:
        return 0.0
    return float(np.median(np.abs(d - np.median(d))) / (0.6745 * np.sqrt(2.0)))


def local_noise_curve(y_raw: np.ndarray) -> tuple[np.ndarray, float]:
    """局部噪声曲线 σ(x) = c·√N(x)，N 为原始计数。

    计数数据噪声随 √N 增长（泊松），全局常数 σ 会低估高计数区。
    标定系数 c = 全局MAD噪声 / median(√N)：真泊松数据 c≈1；
    非计数型数据（已归一等）由 c 自动吸收比例差异。
    返回 (σ(x) 曲线, 标定后的中位噪声)。
    """
    n = np.clip(np.asarray(y_raw, dtype=float), 1.0, None)
    root_n = np.sqrt(n)
    sigma_global = estimate_noise_sigma(y_raw)
    med_root = float(np.median(root_n))
    c = sigma_global / med_root if med_root > 0 else 1.0
    return c * root_n, float(c * med_root)


def _refine_parabolic(x: np.ndarray, y: np.ndarray, idx: int) -> tuple[float, float]:
    """在 idx 附近 ±2 点内取未平滑谱的局部最大，再三点抛物线细化。

    返回 (细化峰位, 局部最大高度)。边缘点退化为原始采样值。
    """
    lo = max(1, idx - 2)
    hi = min(len(y) - 2, idx + 2)
    i = lo + int(np.argmax(y[lo:hi + 1]))
    y0, y1, y2 = y[i - 1], y[i], y[i + 1]
    denom = y0 - 2.0 * y1 + y2
    if abs(denom) < 1e-12:
        return float(x[i]), float(y1)
    delta = 0.5 * (y0 - y2) / denom
    step = float(x[i + 1] - x[i])
    return float(x[i] + delta * step), float(y1)


def detect_peaks(
    two_theta_deg: np.ndarray,
    y_bg_subtracted: np.ndarray,
    detection_threshold_rel: float = DEFAULT_THRESHOLD_REL,
    instrument_fwhm_deg: float = 0.1,
    noise_sigma_factor: float = DEFAULT_NOISE_SIGMA_FACTOR,
    y_raw_for_noise: np.ndarray | None = None,
) -> PeakList:
    """在去背景谱上寻峰。阈值、噪声倍数与仪器展宽均为显式参数。

    噪声水平优先在 y_raw_for_noise（去背景前的原始谱）上估计：
    AsLS 背景会吸收部分噪声使残差方差被低估且分布正偏；
    且计数噪声随 √N 增长，故用局部曲线 σ(x)=c·√N(x) 而非全局常数，
    有效阈值曲线 = max(相对阈值, k·σ(x))。
    """
    x = np.asarray(two_theta_deg, dtype=float)
    y = np.asarray(y_bg_subtracted, dtype=float)
    if len(x) < 7 or float(np.max(y)) <= 0:
        return PeakList([])

    y_max = float(np.max(y))
    rel_floor = detection_threshold_rel / 100.0 * y_max
    if y_raw_for_noise is not None:
        sigma_curve, sigma_med = local_noise_curve(np.asarray(y_raw_for_noise, dtype=float))
        height_curve = np.maximum(rel_floor, noise_sigma_factor * sigma_curve)
        sigma = sigma_med
    else:
        sigma = estimate_noise_sigma(y)
        height_curve = np.maximum(rel_floor, noise_sigma_factor * sigma)
    height_abs = float(np.max(height_curve))

    step = float(np.median(np.diff(x)))
    fwhm_pts = max(1.0, instrument_fwhm_deg / step)
    min_width_pts = max(1, int(round(fwhm_pts / 3.0)))

    # 平滑仅用于检测定位；窗长约一个 FWHM，不用于峰位/峰高
    win = int(round(fwhm_pts))
    win = max(5, win + (win % 2 == 0))
    win = min(win, len(y) - 1 + (len(y) % 2 == 0))
    if win >= 5:
        y_det = savgol_filter(y, win, 2)
    else:
        y_det = y

    idx, _ = find_peaks(y_det, height=height_curve, prominence=height_curve,
                        width=min_width_pts)
    if len(idx) == 0:
        return PeakList(noise_sigma=sigma, threshold_abs=height_abs)

    # 峰位与峰高取自未平滑谱
    refined = [_refine_parabolic(x, y, i) for i in idx]
    pos = np.array([r[0] for r in refined])
    heights = np.array([r[1] for r in refined])

    widths, _, _, _ = peak_widths(y_det, idx, rel_height=0.5)
    fwhm_deg = widths * step

    # 归一化：只缩放强度，峰位不变
    intens_norm = 100.0 * heights / float(np.max(heights))

    peaks = [
        Peak(two_theta_deg=float(p), intensity_norm=float(i_n),
             height_abs=float(h), fwhm_deg=float(w))
        for p, i_n, h, w in zip(pos, intens_norm, heights, fwhm_deg)
    ]
    peaks.sort(key=lambda p: p.two_theta_deg)
    return PeakList(peaks, noise_sigma=sigma, threshold_abs=height_abs)
