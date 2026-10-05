"""FastAPI 主应用：离线 XRD 复核台后端。

分析流水线（每步参数显式、结果全部回显）：
  原始谱 → 零点偏移校正 → AsLS 背景估计 → 去背景谱 → 寻峰(阈值/展宽显式)
  → 强度归一(不动峰位) → 与库内全部参考条目逐一匹配 → 返回候选列表+证据。
"""
from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager

import numpy as np
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from .database import get_db
from .models import ReferencePattern, ReferencePeak
from .schemas import (AnalysisParams, AnalyzeRequest, ReferenceIn, ReferenceOut,
                      SyntheticRequest)
from .seed import init_db, seed_if_empty
from .xrd.background import als_background
from .xrd.matching import RefPeak, auto_tolerance, match_one, rank_candidates
from .xrd.peaks import detect_peaks
from .xrd.synthetic import synthetic_spectrum
from .xrd.units import apply_zero_offset, two_theta_to_d

DISCLAIMER = ("本工具仅用于课程教学中的谱线对照练习：匹配结果按透明规则排序，"
              "列出每个候选的命中、缺失与未解释峰，不构成也不替代真实材料鉴定。"
              "参考数据为教科书公开值或自制示例，未使用任何付费数据库。")

CONVENTIONS = {
    "angle_unit": "degree, 2θ",
    "wavelength_unit": "angstrom",
    "zero_offset_convention": "corrected_2theta = measured_2theta - zero_offset_deg",
    "normalization": "peak intensities scaled to max=100; peak positions unchanged",
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 数据库可能尚未就绪（compose 启动竞态），有限次重试
    last_err: Exception | None = None
    for _ in range(30):
        try:
            init_db()
            db = next(get_db())
            try:
                seed_if_empty(db)
            finally:
                db.close()
            last_err = None
            break
        except Exception as err:  # noqa: BLE001 - 启动期兜底重试
            last_err = err
            time.sleep(2)
    if last_err is not None:
        raise last_err
    yield


app = FastAPI(title="Offline XRD Review Bench", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health():
    return {"status": "ok", "conventions": CONVENTIONS, "disclaimer": DISCLAIMER}


@app.get("/api/references", response_model=list[ReferenceOut])
def list_references(db: Session = Depends(get_db)):
    return db.query(ReferencePattern).all()


@app.post("/api/references", response_model=ReferenceOut, status_code=201)
def create_reference(payload: ReferenceIn, db: Session = Depends(get_db)):
    if not payload.peaks:
        raise HTTPException(400, "at least one peak required")
    pat = ReferencePattern(name=payload.name, formula=payload.formula,
                           source=payload.source, note=payload.note)
    pat.peaks = [ReferencePeak(d_angstrom=p.d_angstrom, intensity_rel=p.intensity_rel)
                 for p in payload.peaks]
    db.add(pat)
    db.commit()
    db.refresh(pat)
    return pat


def _run_pipeline(req: AnalyzeRequest, db: Session) -> dict:
    x = np.asarray(req.two_theta_deg, dtype=float)
    y = np.asarray(req.intensity, dtype=float)
    if len(x) < 10 or len(x) != len(y):
        raise HTTPException(400, "two_theta_deg and intensity must have equal length >= 10")
    order = np.argsort(x)
    x, y = x[order], y[order]

    p = req.params
    # 1) 零点偏移校正（只平移角度轴）
    x_corr = apply_zero_offset(x, p.zero_offset_deg)
    # 2) 背景估计（AsLS，参数显式）
    bg = als_background(y, lam=p.bg_lam, p=p.bg_p)
    y_sub = y - bg
    # 3) 寻峰（阈值与仪器展宽显式；归一化在寻峰内部完成，只缩放强度）
    peak_list = detect_peaks(x_corr, y_sub,
                             detection_threshold_rel=p.detection_threshold_rel,
                             instrument_fwhm_deg=p.instrument_fwhm_deg,
                             noise_sigma_factor=p.noise_sigma_factor,
                             y_raw_for_noise=y)
    for pk in peak_list.peaks:
        pk.d_angstrom = float(two_theta_to_d(pk.two_theta_deg, p.wavelength_angstrom))
    # 4) 匹配容差：显式给定或自动
    tol = p.match_tolerance_deg if p.match_tolerance_deg is not None \
        else auto_tolerance(p.instrument_fwhm_deg)

    sample_range = (float(x_corr[0]), float(x_corr[-1]))
    refs = db.query(ReferencePattern).all()
    reports = []
    for ref in refs:
        ref_peaks = [RefPeak(d_angstrom=rp.d_angstrom, intensity_rel=rp.intensity_rel)
                     for rp in ref.peaks]
        reports.append(match_one(
            peak_list, ref_peaks, ref.id, ref.name, ref.formula,
            wavelength_angstrom=p.wavelength_angstrom,
            sample_range_deg=sample_range,
            detection_threshold_rel=p.detection_threshold_rel,
            tolerance_deg=tol,
        ))
    ranked = rank_candidates(reports)

    return {
        "conventions": {**CONVENTIONS,
                        "wavelength_angstrom": p.wavelength_angstrom,
                        "zero_offset_deg": p.zero_offset_deg,
                        "instrument_fwhm_deg": p.instrument_fwhm_deg,
                        "detection_threshold_rel": p.detection_threshold_rel,
                        "noise_sigma_factor": p.noise_sigma_factor,
                        "match_tolerance_deg": tol,
                        "bg_lam": p.bg_lam, "bg_p": p.bg_p},
        "raw": {"two_theta_deg": x_corr.tolist(), "intensity": y.tolist()},
        "background": bg.tolist(),
        "background_subtracted": y_sub.tolist(),
        "peaks": [{"two_theta_deg": pk.two_theta_deg,
                   "intensity_norm": pk.intensity_norm,
                   "height_abs": pk.height_abs,
                   "fwhm_deg": pk.fwhm_deg,
                   "d_angstrom": pk.d_angstrom} for pk in peak_list.peaks],
        "candidates": [{
            "reference_id": r.reference_id, "name": r.name, "formula": r.formula,
            "score": r.score, "coverage": r.coverage,
            "explained_fraction": r.explained_fraction,
            "n_matched": r.n_matched,
            "mean_abs_delta_deg": r.mean_abs_delta,
            "tolerance_deg": r.tolerance_deg,
            "matched": [vars(m) for m in r.matched],
            "missing_ref_peaks": [
                {"d_angstrom": rp.d_angstrom, "intensity_rel": rp.intensity_rel,
                 "two_theta_deg": rp.two_theta_deg} for rp in r.missing_ref_peaks],
            "unexplained_sample_peaks": r.unexplained_sample_peaks,
        } for r in ranked],
        "disclaimer": DISCLAIMER,
    }


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest, db: Session = Depends(get_db)):
    return _run_pipeline(req, db)


@app.post("/api/synthetic")
def synthetic(req: SyntheticRequest, db: Session = Depends(get_db)):
    """从库内参考条目生成合成测试谱（单相/系统偏移/宽峰三类案例都走这里）。"""
    ref = db.get(ReferencePattern, req.reference_id)
    if ref is None:
        raise HTTPException(404, "reference not found")
    peaks = [(rp.d_angstrom, rp.intensity_rel) for rp in ref.peaks]
    x, measured, clean = synthetic_spectrum(
        peaks,
        wavelength_angstrom=req.params.wavelength_angstrom,
        fwhm_deg=req.fwhm_deg,
        zero_offset_deg=req.zero_offset_deg,
        max_counts=req.max_counts,
        seed=req.seed,
    )
    return {
        "two_theta_deg": x.tolist(),
        "intensity": measured.tolist(),
        "clean_intensity": clean.tolist(),
        "generated_with": {
            "reference_id": ref.id, "name": ref.name,
            "fwhm_deg": req.fwhm_deg, "zero_offset_deg": req.zero_offset_deg,
            "wavelength_angstrom": req.params.wavelength_angstrom,
            "note": "合成谱仅用于流程测试，峰位=参考值+指定偏移",
        },
    }


# 生产模式：若前端已构建，由后端直接托管静态文件
_dist = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
if os.path.isdir(_dist):
    app.mount("/", StaticFiles(directory=_dist, html=True), name="frontend")
