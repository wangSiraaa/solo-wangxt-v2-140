"""三类必需测试案例 + 关键不变量。

1. 单相合成谱：由某参考条目生成的谱，该条目应排在候选首位且覆盖率高；
2. 系统偏移：峰位整体 +0.15°，不设零点校正时匹配退化或残差增大，
   设置 zero_offset_deg=0.15 后恢复；
3. 宽峰：FWHM=0.6° 时，显式传入 instrument_fwhm_deg，自动容差随之放大，
   仍能正确匹配；
另验证：归一化不改峰位；缺失峰与未解释峰都被列出；API 端到端可用。
"""
from __future__ import annotations

import os

import numpy as np
import pytest

os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app.xrd.background import als_background          # noqa: E402
from app.xrd.matching import RefPeak, auto_tolerance, match_one  # noqa: E402
from app.xrd.peaks import detect_peaks                 # noqa: E402
from app.xrd.synthetic import synthetic_spectrum       # noqa: E402
from app.xrd.units import (DEFAULT_WAVELENGTH_ANGSTROM, apply_zero_offset,  # noqa: E402
                           d_to_two_theta)

WL = DEFAULT_WAVELENGTH_ANGSTROM

# 教学用石英主峰 (d Å, I)
QUARTZ = [(4.255, 20), (3.343, 100), (2.458, 8), (2.282, 8), (2.237, 4),
          (2.128, 6), (1.980, 3), (1.817, 14), (1.672, 4), (1.659, 5),
          (1.608, 3), (1.541, 9), (1.453, 6), (1.382, 8), (1.375, 6)]
# 方解石（干扰项，用于确认不会误判）
CALCITE = [(3.857, 12), (3.035, 100), (2.845, 3), (2.495, 14), (2.285, 18),
           (2.095, 18), (1.913, 17), (1.875, 17), (1.626, 4), (1.604, 5),
           (1.587, 5), (1.525, 3)]


def _analyze(x, y, zero_offset=0.0, fwhm=0.1, threshold=1.0, tol=None):
    x_c = apply_zero_offset(x, zero_offset)
    bg = als_background(y)
    y_sub = y - bg
    peaks = detect_peaks(x_c, y_sub, detection_threshold_rel=threshold,
                         instrument_fwhm_deg=fwhm, y_raw_for_noise=y)
    return x_c, peaks, (tol if tol is not None else auto_tolerance(fwhm))


def _refs():
    return ([RefPeak(d, i) for d, i in QUARTZ],
            [RefPeak(d, i) for d, i in CALCITE])


def _report(peaks, ref_peaks, name, x_c, tol, threshold=1.0):
    return match_one(peaks, ref_peaks, 0, name, "",
                     wavelength_angstrom=WL,
                     sample_range_deg=(float(x_c[0]), float(x_c[-1])),
                     detection_threshold_rel=threshold,
                     tolerance_deg=tol)


# ---------- 案例 1：单相合成谱 ----------

def test_single_phase_synthetic_ranks_source_first():
    x, y, _ = synthetic_spectrum(QUARTZ, WL, fwhm_deg=0.08, seed=1)
    x_c, peaks, tol = _analyze(x, y, fwhm=0.08)
    quartz_ref, calcite_ref = _refs()
    rq = _report(peaks, quartz_ref, "quartz", x_c, tol)
    rc = _report(peaks, calcite_ref, "calcite", x_c, tol)

    assert rq.score > rc.score, "合成石英谱应优先匹配石英而非方解石"
    assert rq.coverage > 0.9, f"石英参考峰覆盖率应>0.9，实际 {rq.coverage}"
    assert rq.explained_fraction > 0.9
    # 峰位误差应在亚步长量级
    assert rq.mean_abs_delta is not None and rq.mean_abs_delta < 0.02


def test_normalization_does_not_move_positions():
    x, y, _ = synthetic_spectrum(QUARTZ, WL, fwhm_deg=0.08, noise=False)
    _, peaks_a, _ = _analyze(x, y, fwhm=0.08)
    _, peaks_b, _ = _analyze(x, 7.5 * y, fwhm=0.08)   # 整体缩放强度
    pa = [p.two_theta_deg for p in peaks_a.peaks]
    pb = [p.two_theta_deg for p in peaks_b.peaks]
    assert pa == pytest.approx(pb, abs=1e-9), "强度缩放不得改变峰位"
    assert max(p.intensity_norm for p in peaks_a.peaks) == pytest.approx(100.0)


# ---------- 案例 2：系统偏移 ----------

def test_systematic_offset_detected_and_corrected():
    shift = 0.15
    x, y, _ = synthetic_spectrum(QUARTZ, WL, fwhm_deg=0.08,
                                 zero_offset_deg=shift, seed=2)
    quartz_ref, _ = _refs()

    # 不校正：残差应反映约 0.15° 的系统偏移（容差放大到 0.2 才能配上）
    x_c0, peaks0, _ = _analyze(x, y, fwhm=0.08, tol=0.2)
    r0 = _report(peaks0, [RefPeak(d, i) for d, i in QUARTZ], "q", x_c0, 0.2)
    assert r0.mean_abs_delta == pytest.approx(shift, abs=0.02)

    # 校正 zero_offset=0.15 后：残差回到亚步长量级
    x_c1, peaks1, tol1 = _analyze(x, y, zero_offset=shift, fwhm=0.08)
    r1 = _report(peaks1, [RefPeak(d, i) for d, i in QUARTZ], "q", x_c1, tol1)
    assert r1.mean_abs_delta is not None and r1.mean_abs_delta < 0.02
    assert r1.coverage > 0.9


# ---------- 案例 3：宽峰 ----------

def test_broad_peaks_match_with_explicit_fwhm():
    x, y, _ = synthetic_spectrum(QUARTZ, WL, fwhm_deg=0.6, step_deg=0.05, seed=3)
    # 仪器展宽作为显式参数传入，自动容差 = max(0.05, 0.5*FWHM) = 0.3°
    x_c, peaks, tol = _analyze(x, y, fwhm=0.6, threshold=2.0)
    assert tol == pytest.approx(0.3)
    quartz_ref, calcite_ref = _refs()
    rq = _report(peaks, quartz_ref, "quartz", x_c, tol, threshold=2.0)
    rc = _report(peaks, calcite_ref, "calcite", x_c, tol, threshold=2.0)
    assert rq.score > rc.score
    assert rq.coverage > 0.8, f"宽峰下覆盖率应>0.8，实际 {rq.coverage}"


# ---------- 证据列表：缺失峰与未解释峰 ----------

def test_missing_and_unexplained_peaks_listed():
    # 石英谱 + 一个不属于石英的人工杂峰
    extra = [(1.30, 60)]  # d=1.30 Å 不在石英列表中
    x, y, _ = synthetic_spectrum(QUARTZ + extra, WL, fwhm_deg=0.08, seed=4)
    x_c, peaks, tol = _analyze(x, y, fwhm=0.08)
    quartz_ref, _ = _refs()
    r = _report(peaks, quartz_ref, "quartz", x_c, tol)

    # 杂峰必须出现在"未解释样品峰"里
    unexplained_pos = [u["two_theta_deg"] for u in r.unexplained_sample_peaks]
    tt_extra = float(d_to_two_theta(1.30, WL))
    assert any(abs(p - tt_extra) < 0.05 for p in unexplained_pos), \
        "样品中的未知峰必须列出"

    # 删掉样品中的最强峰区域 -> 参考有而样品未见必须列出
    mask = ~((x > 26.0) & (x < 27.2))   # 石英 3.343 Å ≈ 26.64°
    x2, y2 = x[mask], y[mask]
    x_c2, peaks2, tol2 = _analyze(x2, y2, fwhm=0.08)
    r2 = _report(peaks2, [RefPeak(d, i) for d, i in QUARTZ], "q", x_c2, tol2)
    missing_d = [m.d_angstrom for m in r2.missing_ref_peaks]
    assert any(abs(d - 3.343) < 1e-3 for d in missing_d), \
        "参考有而样品未见的峰必须列出"


# ---------- API 端到端 ----------

@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:   # 上下文管理器形式才会执行 lifespan（建表+种子）
        yield c


def test_api_end_to_end(client):
    refs = client.get("/api/references").json()
    assert len(refs) >= 6
    quartz = next(r for r in refs if "Quartz" in r["name"])

    syn = client.post("/api/synthetic", json={
        "reference_id": quartz["id"], "fwhm_deg": 0.08,
        "params": {"wavelength_angstrom": WL},
    }).json()
    assert len(syn["two_theta_deg"]) == len(syn["intensity"])

    res = client.post("/api/analyze", json={
        "two_theta_deg": syn["two_theta_deg"],
        "intensity": syn["intensity"],
        "params": {"wavelength_angstrom": WL, "instrument_fwhm_deg": 0.08},
    })
    assert res.status_code == 200
    body = res.json()
    assert body["candidates"][0]["name"] == quartz["name"]
    # 原始谱与去背景谱并列返回
    assert len(body["raw"]["intensity"]) == len(body["background_subtracted"])
    # 约定与免责声明必须显式出现
    assert body["conventions"]["angle_unit"] == "degree, 2θ"
    assert "zero_offset" in body["conventions"]["zero_offset_convention"]
    assert "不构成" in body["disclaimer"] or "不替代" in body["disclaimer"]
    # 每个候选都有缺失/未解释列表字段（即使为空）
    for c in body["candidates"]:
        assert "missing_ref_peaks" in c and "unexplained_sample_peaks" in c
