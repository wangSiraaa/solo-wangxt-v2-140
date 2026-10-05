"""角度单位、波长与零点偏移的显式处理。

本模块只做单位换算与约定说明，不隐含任何默认波长：
调用方必须显式给出波长及其单位。

约定（在整个系统中统一）
-----------------------
* 内部所有角度一律使用 **2θ 角度制（degrees）**。
* 入射波长 wavelength 与 wavelength_unit 同时给出：
    wavelength_unit = "angstrom"（默认，Å）或 "nm"。
* 零点偏移 zero_shift（角度制，°）按仪器读数减真实值定义，
  即  2θ_true = 2θ_measured - zero_shift。
  因此对样本角轴做校正时执行  x_corrected = x_measured - zero_shift。
* angle_unit 允许 "2theta_deg"（默认）、"theta_deg"、"2theta_rad"、"theta_rad"。
  θ 一律乘 2 转为 2θ；弧度一律转角度。
"""

from __future__ import annotations

import math

ANGLE_UNITS = ("2theta_deg", "theta_deg", "2theta_rad", "theta_rad")
WAVELENGTH_UNITS = ("angstrom", "nm")


def to_two_theta_deg(x, angle_unit: str):
    """把任意受支持的角度表示转换为 2θ 角度制数组。

    返回 numpy 数组。原数组不被修改（峰位置永远只来自原始/校正后的角轴，
    绝不允许归一化等强度操作改动它）。
    """
    import numpy as np

    if angle_unit not in ANGLE_UNITS:
        raise ValueError(f"不支持的角度单位 {angle_unit!r}，允许：{', '.join(ANGLE_UNITS)}")
    arr = np.asarray(x, dtype=float)
    if angle_unit.startswith("theta"):
        arr = 2.0 * arr
    if angle_unit.endswith("rad"):
        arr = np.degrees(arr)
    return arr


def wavelength_to_angstrom(wavelength: float, wavelength_unit: str) -> float:
    """将波长换算为埃（Å）。1 nm = 10 Å。"""
    if wavelength_unit not in WAVELENGTH_UNITS:
        raise ValueError(
            f"不支持的波长单位 {wavelength_unit!r}，允许：{', '.join(WAVELENGTH_UNITS)}"
        )
    if wavelength is None or wavelength <= 0:
        raise ValueError("波长必须为正数，且必须显式提供（不隐含默认靶材）")
    return wavelength * 10.0 if wavelength_unit == "nm" else float(wavelength)


def apply_zero_shift(two_theta_deg, zero_shift: float):
    """对 2θ 角轴施加零点偏移校正：x_corrected = x_measured - zero_shift。"""
    import numpy as np

    return np.asarray(two_theta_deg, dtype=float) - float(zero_shift)


def bragg_two_theta_deg(d_spacing_angstrom: float, wavelength_angstrom: float) -> float:
    """由晶面间距 d（Å）和波长（Å）计算 2θ（角度制）。

    遵循布拉格定律 nλ = 2d sinθ（n=1）。超过衍射极限（λ > 2d）时抛错，
    而不是静默忽略——调用方负责决定如何处理不可见峰。
    """
    if wavelength_angstrom <= 0 or d_spacing_angstrom <= 0:
        raise ValueError("d 与波长必须为正数")
    ratio = wavelength_angstrom / (2.0 * d_spacing_angstrom)
    if ratio > 1.0:
        raise ValueError(
            f"λ={wavelength_angstrom:.4f}Å 对 d={d_spacing_angstrom:.4f}Å 超出衍射极限"
        )
    return 2.0 * math.degrees(math.asin(ratio))


def describe_convention(
    wavelength: float,
    wavelength_unit: str,
    angle_unit: str,
    zero_shift: float,
) -> dict:
    """生成随结果一起返回的单位约定说明，避免任何歧义。"""
    return {
        "wavelength": wavelength,
        "wavelength_unit": wavelength_unit,
        "wavelength_angstrom": wavelength_to_angstrom(wavelength, wavelength_unit),
        "input_angle_unit": angle_unit,
        "internal_angle_unit": "2theta_deg",
        "zero_shift_deg": zero_shift,
        "zero_shift_convention": "2theta_true = 2theta_measured - zero_shift",
    }
