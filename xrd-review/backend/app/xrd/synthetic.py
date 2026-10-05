"""合成测试谱生成：用于三类测试案例（单相合成谱、系统偏移、宽峰）。

谱 = 高斯峰簇（按参考 d/强度，叠加零点偏移与指定 FWHM）
     + 教学用背景（缓变隆起 + 线性项）+ 泊松噪声。
"""
from __future__ import annotations

import numpy as np

from .units import d_to_two_theta


def synthetic_spectrum(
    ref_peaks: list[tuple[float, float]],   # (d Å, 相对强度 0-100)
    wavelength_angstrom: float,
    fwhm_deg: float,
    zero_offset_deg: float = 0.0,
    two_theta_min: float = 10.0,
    two_theta_max: float = 90.0,
    step_deg: float = 0.02,
    max_counts: float = 3000.0,
    background_amplitude: float = 300.0,
    noise: bool = True,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """返回 (2θ轴, 含背景含噪声的"实测"谱, 无噪声净谱)。"""
    x = np.arange(two_theta_min, two_theta_max + step_deg / 2, step_deg)
    y = np.zeros_like(x)
    for d, inten in ref_peaks:
        tt = float(d_to_two_theta(d, wavelength_angstrom))
        if np.isnan(tt) or not (two_theta_min <= tt + zero_offset_deg <= two_theta_max):
            continue
        center = tt + zero_offset_deg          # 系统偏移直接加在峰位上
        sigma = fwhm_deg / (2.0 * np.sqrt(2.0 * np.log(2.0)))
        y += (inten / 100.0) * max_counts * np.exp(-0.5 * ((x - center) / sigma) ** 2)

    # 背景：低角缓变隆起 + 线性漂移（教学用，不代表真实仪器）
    bg = (background_amplitude * np.exp(-(x - two_theta_min) / 15.0)
          + 0.5 * background_amplitude * (1.0 - (x - two_theta_min) / (two_theta_max - two_theta_min)))

    clean = y + bg
    if noise:
        rng = np.random.default_rng(seed)
        measured = rng.poisson(np.clip(clean, 0, None)).astype(float)
    else:
        measured = clean
    return x, measured, clean
