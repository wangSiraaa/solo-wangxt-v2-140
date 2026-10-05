"""Pydantic 模式：请求/响应中显式携带波长、角度单位、零点偏移等约定。"""
from __future__ import annotations

from pydantic import BaseModel, Field

from .xrd.units import DEFAULT_WAVELENGTH_ANGSTROM


class ReferencePeakIn(BaseModel):
    d_angstrom: float = Field(gt=0)
    intensity_rel: float = Field(ge=0, le=100)


class ReferenceIn(BaseModel):
    name: str
    formula: str = ""
    source: str = "self-made teaching example"
    note: str = ""
    peaks: list[ReferencePeakIn]


class ReferenceOut(BaseModel):
    id: int
    name: str
    formula: str
    source: str
    note: str
    peaks: list[ReferencePeakIn]

    model_config = {"from_attributes": True}


class AnalysisParams(BaseModel):
    """全部显式参数。角度单位固定为度(2θ)，波长按 Å。"""
    wavelength_angstrom: float = Field(DEFAULT_WAVELENGTH_ANGSTROM, gt=0)
    angle_unit: str = Field("deg_2theta", pattern="^deg_2theta$")  # 当前仅支持度
    zero_offset_deg: float = 0.0
    instrument_fwhm_deg: float = Field(0.1, gt=0)
    detection_threshold_rel: float = Field(1.0, ge=0, le=100)  # % of max
    noise_sigma_factor: float = Field(5.0, ge=0)               # 噪声下限倍数
    match_tolerance_deg: float | None = None                    # None -> 自动
    bg_lam: float = Field(1.0e5, gt=0)
    bg_p: float = Field(0.01, gt=0, lt=1)


class AnalyzeRequest(BaseModel):
    two_theta_deg: list[float]
    intensity: list[float]
    params: AnalysisParams = AnalysisParams()


class SyntheticRequest(BaseModel):
    reference_id: int
    params: AnalysisParams = AnalysisParams()
    zero_offset_deg: float = 0.0      # 生成谱时注入的系统偏移
    fwhm_deg: float = 0.1             # 生成谱的峰宽（可与分析参数不同）
    max_counts: float = 3000.0
    seed: int = 42
