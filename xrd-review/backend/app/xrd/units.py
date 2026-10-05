"""单位与几何约定 —— 所有约定在此集中定义，其他地方不得另起炉灶。

约定（必须在报告与 API 中显式出现）：
- 角度单位：度 (degree)，扫描轴为 2θ。
- 波长单位：埃 (Å)，默认 Cu Kα = 1.5406 Å。
- 零点偏移约定：corrected_2theta = measured_2theta - zero_offset_deg。
  即样品峰位系统性偏高时 zero_offset 为正。
- d 间距单位：Å，布拉格定律 lambda = 2 d sin(theta)。
"""
from __future__ import annotations

import numpy as np

DEFAULT_WAVELENGTH_ANGSTROM = 1.5406  # Cu Kα1


def d_to_two_theta(d_angstrom: np.ndarray | float, wavelength_angstrom: float) -> np.ndarray:
    """d(Å) -> 2θ(度)。d 过小（sin 超过 1）时返回 NaN，由调用方剔除。"""
    d = np.asarray(d_angstrom, dtype=float)
    s = wavelength_angstrom / (2.0 * d)
    out = np.full_like(s, np.nan)
    ok = s <= 1.0
    out[ok] = 2.0 * np.degrees(np.arcsin(s[ok]))
    return out


def two_theta_to_d(two_theta_deg: np.ndarray | float, wavelength_angstrom: float) -> np.ndarray:
    """2θ(度) -> d(Å)。"""
    tt = np.asarray(two_theta_deg, dtype=float)
    return wavelength_angstrom / (2.0 * np.sin(np.radians(tt) / 2.0))


def apply_zero_offset(two_theta_deg: np.ndarray, zero_offset_deg: float) -> np.ndarray:
    """应用零点偏移校正：corrected = measured - zero_offset。

    只平移角度轴，不改变强度，也不改变峰形。
    """
    return np.asarray(two_theta_deg, dtype=float) - float(zero_offset_deg)
