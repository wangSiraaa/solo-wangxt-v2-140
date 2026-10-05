"""把 API 请求组装为分析流水线调用。"""

from __future__ import annotations

from .db import DB
from .xrd.io_utils import parse_spectrum_text
from .xrd.pipeline import run_analysis
from .xrd.units import wavelength_to_angstrom


def load_reference_set(db: DB, codes: list[str] | None):
    refs = []
    ref_peaks = {}
    for row in db.list_references():
        if codes and row["code"] not in codes:
            continue
        bundle = db.get_reference_with_peaks(row["code"])
        refs.append(bundle["reference"])
        ref_peaks[row["code"]] = bundle["peaks"]
    if not refs:
        raise ValueError("没有可用参考条目（库为空或指定的 code 均不存在）")
    return refs, ref_peaks


def analyze_from_request(req, db: DB) -> dict:
    # 数据来源：显式数组优先，其次 CSV 文本
    if req.two_theta is not None and req.intensity is not None:
        two_theta, intensity = req.two_theta, req.intensity
    elif req.spectrum_text:
        parsed = parse_spectrum_text(req.spectrum_text)
        two_theta, intensity = parsed["two_theta"], parsed["intensity"]
    else:
        raise ValueError("必须提供 two_theta/intensity 数组或 spectrum_text CSV 文本")

    refs, ref_peaks = load_reference_set(db, req.reference_codes)

    result = run_analysis(
        two_theta,
        intensity,
        refs,
        ref_peaks,
        wavelength=req.wavelength,
        wavelength_unit=req.wavelength_unit,
        angle_unit=req.angle_unit,
        zero_shift=req.zero_shift,
        bg_window=req.bg_window,
        bg_iterations=req.bg_iterations,
        bg_smoothing=req.bg_smoothing,
        prominence_sigma=req.prominence_sigma,
        min_separation_deg=req.min_separation_deg,
        min_fwhm_deg=req.min_fwhm_deg,
        max_fwhm_deg=req.max_fwhm_deg,
        instrument_fwhm_deg=req.instrument_fwhm_deg,
        uncertainty_fraction=req.uncertainty_fraction,
        tolerance_deg=req.tolerance_deg,
        minimum_hits=req.minimum_hits,
        shift_scan_max=req.shift_scan_max,
        shift_scan_step=req.shift_scan_step,
    )
    result["used_wavelength_angstrom"] = wavelength_to_angstrom(
        req.wavelength, req.wavelength_unit
    )

    run_id = None
    if req.save_label and not db.memory:
        run_id = db.save_run(req.save_label, req.model_dump(), result)
    result["run_id"] = run_id
    return result
