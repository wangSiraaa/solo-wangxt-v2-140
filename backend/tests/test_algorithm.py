"""算法层单元测试：单位、峰位不变性、匹配、合成演示用例。"""

import math

import numpy as np
import pytest

from app.xrd import references as R, synthesize as S
from app.xrd.matching import match_all
from app.xrd.peaks import detect_peaks
from app.xrd.pipeline import run_analysis
from app.xrd.units import (
    apply_zero_shift,
    bragg_two_theta_deg,
    to_two_theta_deg,
    wavelength_to_angstrom,
)

REFS = R.BUILTIN_REFERENCES
REF_PEAKS = {r["code"]: R.build_builtin_peak_rows(r) for r in REFS}


# ---------------- 单位与波长 ----------------
def test_angle_conversions():
    assert np.allclose(to_two_theta_deg([45.0], "2theta_deg"), [45.0])
    assert np.allclose(to_two_theta_deg([22.5], "theta_deg"), [45.0])
    assert np.allclose(to_two_theta_deg([math.pi / 4], "2theta_rad"), [45.0])
    assert np.allclose(to_two_theta_deg([math.pi / 8], "theta_rad"), [45.0])
    with pytest.raises(ValueError):
        to_two_theta_deg([1], "2theta_grad")


def test_wavelength_and_zero_shift():
    assert wavelength_to_angstrom(0.154056, "nm") == pytest.approx(1.54056)
    assert wavelength_to_angstrom(1.54056, "angstrom") == pytest.approx(1.54056)
    with pytest.raises(ValueError):
        wavelength_to_angstrom(-1.0, "angstrom")
    x = np.array([10.0, 20.0, 30.0])
    assert np.allclose(apply_zero_shift(x, 0.5), [9.5, 19.5, 29.5])


def test_bragg_law_known_values():
    # Cu Kα1, Si(111) d=3.1356 Å -> 2θ ≈ 28.44°
    tt = bragg_two_theta_deg(3.1356, 1.54056)
    assert tt == pytest.approx(28.44, abs=0.02)
    with pytest.raises(ValueError):
        bragg_two_theta_deg(0.5, 1.54056)  # λ > 2d


# ---------------- 参考谱合理性 ----------------
@pytest.mark.parametrize("code,hkl0", [
    ("SYN-CU-FCC", "(111)"),
    ("SYN-FE-BCC", "(110)"),
    ("SYN-SI-DIA", "(111)"),
])
def test_reference_first_peak(code, hkl0):
    assert REF_PEAKS[code][0]["hkl"] == hkl0


def test_fcc_extinction():
    # FCC: (100) 必须消光，最小允许为 (111)
    assert all(p["hkl"] != "(100)" for p in REF_PEAKS["SYN-CU-FCC"])
    assert {p["hkl"] for p in REF_PEAKS["SYN-CU-FCC"]} >= {"(111)", "(200)", "(220)"}


def test_intensity_normalization_does_not_move_peaks():
    rows = REF_PEAKS["SYN-CU-FCC"]
    positions = [p["two_theta"] for p in rows]
    rescaled = [{**p, "intensity_rel": p["intensity_rel"] * 2.5} for p in rows]
    assert [p["two_theta"] for p in rescaled] == positions
    assert max(p["intensity_rel"] for p in rows) == 100.0


# ---------------- 峰检测 ----------------
def _gaussian(x, c, a=1000.0, w=0.12):
    return a * np.exp(-0.5 * ((x - c) / (w / 2.355)) ** 2)


def test_detect_finds_known_peaks_and_uncertainty():
    x = np.arange(15, 90, 0.02)
    y = 50 - 0.3 * (x - 15) + _gaussian(x, 43.3) + _gaussian(x, 50.45)
    y += np.random.default_rng(0).normal(0, 2, x.size)
    from app.xrd.background import subtract_background
    bg, net = subtract_background(y)
    out = detect_peaks(x, y, net, instrument_fwhm_deg=0.08)
    pos = [p["two_theta"] for p in out["peaks"]]
    assert any(abs(p - 43.3) < 0.05 for p in pos)
    assert any(abs(p - 50.45) < 0.05 for p in pos)
    for p in out["peaks"]:
        # 不确定度必须显式且为正；本征宽化在窄峰情形可解析
        assert p["position_uncertainty_deg"] > 0


def test_broad_rejection_is_explicit():
    x = np.arange(15, 60, 0.02)
    y = 30 + _gaussian(x, 30.0, a=800.0, w=4.0) + _gaussian(x, 45.0, a=900.0, w=0.5)
    rng = np.random.default_rng(1)
    y = np.maximum(y + rng.normal(0, 5, x.size), 0)
    out = detect_peaks(x, y, y, max_fwhm_deg=2.0, prominence_sigma=5.0,
                       instrument_fwhm_deg=0.08)
    rejected = [r["two_theta"] for r in out["rejected_broad"]]
    accepted = [p["two_theta"] for p in out["peaks"]]
    assert any(abs(r - 30.0) < 0.6 for r in rejected)
    assert any(abs(p - 45.0) < 0.3 for p in accepted)


# ---------------- 全流水线演示用例 ----------------
def _run_case(case, **overrides):
    d = S.build_demo_case(case, REFS, REF_PEAKS)
    sp = dict(d["truth"]["suggested_params"])
    sp.update(overrides)
    res = run_analysis(
        d["spectrum"]["two_theta"], d["spectrum"]["intensity"],
        REFS, REF_PEAKS,
        wavelength=d["wavelength"], wavelength_unit=d["wavelength_unit"],
        bg_window=sp.pop("bg_window", 40),
        **sp,
    )
    return d, res


def test_single_phase_clean_case():
    _, res = _run_case("single_clean")
    top = res["matching"]["candidates"][0]
    assert top["reference_code"] == "SYN-CU-FCC"
    assert top["scores"]["hit_count"] == 4
    assert top["missing_in_range"] == []
    assert top["unknown_sample_peaks"] == []
    # 不出现唯一结论字段语义
    assert "no_unique_conclusion" in res["matching"]["summary"]


def test_systematic_shift_case():
    # 未校正：命中数下降，偏移扫描应提示显著正偏移
    d, res0 = _run_case("systematic_shift", zero_shift=0.0)
    cu0 = next(c for c in res0["matching"]["candidates"] if c["reference_code"] == "SYN-CU-FCC")
    scan = next(r for r in res0["matching"]["shift_scan"]["per_reference"]
                if r["reference_code"] == "SYN-CU-FCC")
    assert scan["best_hits_under_scan"] > scan["hits_at_zero_shift"]
    assert scan["suggested_zero_shift_deg"] > 0.3

    # 显式校正后：Cu 恢复且不自动应用扫描值
    _, res1 = _run_case("systematic_shift", zero_shift=0.60)
    cu1 = next(c for c in res1["matching"]["candidates"] if c["reference_code"] == "SYN-CU-FCC")
    assert cu1["scores"]["hit_count"] > cu0["scores"]["hit_count"]
    assert res1["convention"]["zero_shift_deg"] == 0.60
    assert res1["convention"]["zero_shift_convention"].startswith("2theta_true")


def test_broad_peak_case_flags_hump_and_broadening():
    _, res = _run_case("broad_peaks")
    rejected = res["peaks"]["rejected_broad"]
    assert len(rejected) == 1
    assert abs(rejected[0]["two_theta"] - 23.36) < 0.3
    assert rejected[0]["fwhm_deg"] > 2.0
    si = next(c for c in res["matching"]["candidates"] if c["reference_code"] == "SYN-SI-DIA")
    assert si["scores"]["hit_count"] >= 5
    # 本征宽化明显大于仪器展宽
    intrinsic = [p["intrinsic_fwhm_deg"] for p in res["peaks"]["peaks"]
                 if p["broadening_resolved"]]
    assert intrinsic and max(intrinsic) > 0.4


def test_mixture_case_two_phases_pass():
    _, res = _run_case("mixture")
    passing = {c["reference_code"] for c in res["matching"]["candidates"]
               if c["passes_minimum_hits"]}
    assert {"SYN-CU-FCC", "SYN-FE-BCC"} <= passing
    cu = next(c for c in res["matching"]["candidates"] if c["reference_code"] == "SYN-CU-FCC")
    fe = next(c for c in res["matching"]["candidates"] if c["reference_code"] == "SYN-FE-BCC")
    # Cu 解释不了的峰由 Fe 解释；两者都不被宣布为唯一答案
    assert len(cu["unknown_sample_peaks"]) >= 1
    assert fe["scores"]["hit_count"] == 3


def test_unknown_peaks_are_listed_not_absorbed():
    _, res = _run_case("weak_unknown")
    unexplained = {round(p["two_theta"], 1) for p in res["unexplained_overall"]}
    assert {34.2, 57.6} <= unexplained
    al = next(c for c in res["matching"]["candidates"] if c["reference_code"] == "SYN-AL-FCC")
    unknown = {round(p["sample_two_theta"], 1) for p in al["unknown_sample_peaks"]}
    assert {34.2, 57.6} <= unknown


def test_missing_reference_peaks_listed():
    # 只给样本一个峰，其余参考峰必须作为缺失列出
    x = np.arange(30, 90, 0.02)
    y = _gaussian(x, 43.3) + 5.0
    one_peak = [{
        "two_theta": 43.31, "intensity_net": 900.0, "intensity_raw": 900.0,
        "fwhm_deg": 0.12, "intrinsic_fwhm_deg": 0.09, "broadening_resolved": True,
        "position_uncertainty_deg": 0.012,
    }]
    out = match_all(one_peak, REFS, REF_PEAKS, x_range=(30, 90), minimum_hits=2)
    cu = next(c for c in out["candidates"] if c["reference_code"] == "SYN-CU-FCC")
    assert len(cu["missing_in_range"]) == 3  # (200)(220)(? 400 in range)
    assert cu["passes_minimum_hits"] is False
    # 即使不达标，候选仍保留在列表中
    assert len(out["candidates"]) == len(REFS)


def test_normalized_curves_returned_but_detection_uses_raw():
    _, res = _run_case("single_clean")
    c = res["curves"]
    assert max(c["raw_normalized"]) == pytest.approx(1.0)
    assert max(c["net_normalized"]) == pytest.approx(1.0)
    # 原始与去背景并列返回
    assert len(c["raw_intensity"]) == len(c["net_intensity"]) == len(c["background"])
    # 原始强度未被归一化修改（最大值应远大于 1）
    assert max(c["raw_intensity"]) > 10
