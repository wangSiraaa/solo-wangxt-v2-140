"""Pydantic 请求/响应模型。所有物理参数显式给默认值并带说明。"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from .xrd.units import ANGLE_UNITS, WAVELENGTH_UNITS


class AnalyzeRequest(BaseModel):
    # 数据：两列等长数组，或 text 形式的 CSV
    two_theta: Optional[list[float]] = None
    intensity: Optional[list[float]] = None
    spectrum_text: Optional[str] = None
    reference_codes: Optional[list[str]] = None   # None/空=全部库内参考

    # —— 必须明确的物理约定 ——
    wavelength: float = Field(1.54056, description="入射波长；必须显式，默认仅为占位，前端会显示靶材选择")
    wavelength_unit: str = Field("angstrom", description=f"允许：{WAVELENGTH_UNITS}")
    angle_unit: str = Field("2theta_deg", description=f"允许：{ANGLE_UNITS}")
    zero_shift: float = Field(0.0, description="零点偏移(°)，2θ_true=2θ_measured-zero_shift；只用显式值")

    # —— 背景（SNIP）显式参数 ——
    bg_window: int = 40
    bg_iterations: int = 24
    bg_smoothing: int = 3

    # —— 检测阈值与展宽显式参数 ——
    prominence_sigma: float = 3.0
    min_separation_deg: float = 0.05
    min_fwhm_deg: float = 0.03
    max_fwhm_deg: float = 3.0
    instrument_fwhm_deg: float = 0.1
    uncertainty_fraction: float = 0.1

    # —— 匹配显式参数 ——
    tolerance_deg: float = 0.15
    minimum_hits: int = 2
    shift_scan_max: float = 2.0
    shift_scan_step: float = 0.02

    save_label: Optional[str] = None


class PeakListReferenceRequest(BaseModel):
    code: str
    name: str
    wavelength: float
    wavelength_unit: str = "angstrom"
    peaks: list[dict] = Field(
        ...,
        description="每项形如 {two_theta, intensity_rel(0-100), hkl?}；角度单位固定为 2θ°",
    )
    provenance: str = Field(..., description="来源与近似说明（开放数据/自制），不得为空")


class CustomCubicRequest(BaseModel):
    code: str
    name: str
    structure: str = Field(..., description="SC/BCC/FCC/DIAMOND/NACL/CSCL/FLUORITE 之一")
    a_angstrom: float
    wavelength: float
    wavelength_unit: str = "angstrom"
    two_theta_max: float = 90.0
    provenance: str = "用户自定义立方结构合成谱（教学）"


class DemoRequest(BaseModel):
    case: str = Field(
        ...,
        description="single_clean | systematic_shift | broad_peaks | mixture | weak_unknown",
    )


class ReferenceOut(BaseModel):
    code: str
    name: str
    structure: Optional[str] = None
    a_angstrom: Optional[float] = None
    wavelength_angstrom: float
    source: str
    provenance: str
    params: dict[str, Any] = {}
    n_peaks: Optional[int] = None
