"""FastAPI 入口：参考谱管理、谱分析、合成演示用例。

启动：
    uvicorn app.main:app --reload --port 8000
首次启动会自动建表并写入内置开放教学参考谱。
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .db import get_db
from .schemas import (
    AnalyzeRequest,
    CustomCubicRequest,
    DemoRequest,
    PeakListReferenceRequest,
)
from .seed import seed
from .service import analyze_from_request
from .xrd import references as R
from .xrd.synthesize import build_demo_case
from .xrd.units import ANGLE_UNITS, WAVELENGTH_UNITS, wavelength_to_angstrom

app = FastAPI(
    title="离线 XRD 复核台 API",
    version="1.0.0",
    description=(
        "教学用离线 X 射线衍射谱复核：开放/自制参考谱对照、显式波长与展宽参数、"
        "缺失峰与未知峰全列。**不输出自动物相鉴定结论，不访问付费数据库。**"
    ),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    db = get_db()
    db.init_schema()
    if db.count_references() == 0:
        seed(db)


@app.get("/api/health")
def health():
    db = get_db()
    return {
        "status": "ok",
        "storage": "memory(testing fallback)" if db.memory else "postgresql",
        "n_references": db.count_references(),
        "paid_databases_accessed": False,
    }


@app.get("/api/constants")
def constants():
    return {
        "common_targets_angstrom": R.COMMON_TARGETS,
        "angle_units": list(ANGLE_UNITS),
        "wavelength_units": list(WAVELENGTH_UNITS),
        "demo_cases": [
            {"case": "single_clean", "title": "单相合成谱：Cu"},
            {"case": "systematic_shift", "title": "系统偏移：Cu +0.60°"},
            {"case": "broad_peaks", "title": "宽峰：宽化 Si + 无定形鼓包"},
            {"case": "mixture", "title": "两相混合：Cu + α-Fe"},
            {"case": "weak_unknown", "title": "Al + 未知杂质峰"},
        ],
    }


# --------------------------------------------------------------------------
# 参考谱
# --------------------------------------------------------------------------
@app.get("/api/references")
def list_references():
    db = get_db()
    out = []
    for row in db.list_references():
        bundle = db.get_reference_with_peaks(row["code"])
        row = dict(row)
        row["n_peaks"] = len(bundle["peaks"])
        out.append(row)
    return {"references": out}


@app.get("/api/references/{code}")
def get_reference(code: str):
    bundle = get_db().get_reference_with_peaks(code)
    if bundle is None:
        raise HTTPException(404, f"参考条目 {code} 不存在")
    return bundle


@app.post("/api/references/peaklist")
def create_peaklist_reference(req: PeakListReferenceRequest):
    if not req.provenance.strip():
        raise HTTPException(422, "provenance（来源说明）不能为空，自制/开放数据必须可追溯")
    wl_a = wavelength_to_angstrom(req.wavelength, req.wavelength_unit)
    peaks, seen = [], set()
    for i, p in enumerate(req.peaks):
        tt = float(p["two_theta"])
        if not 0 < tt < 180 or tt in seen:
            raise HTTPException(422, f"第 {i} 个峰 two_theta 非法或重复：{tt}")
        seen.add(tt)
        peaks.append(
            {
                "two_theta": round(tt, 4),
                "intensity_rel": float(p.get("intensity_rel", 0)),
                "hkl": p.get("hkl"),
                "d_angstrom": p.get("d_angstrom"),
                "multiplicity": p.get("multiplicity"),
            }
        )
    peaks.sort(key=lambda p: p["two_theta"])
    ref = {
        "code": req.code,
        "name": req.name,
        "structure": "CUSTOM",
        "a_angstrom": None,
        "wavelength_angstrom": wl_a,
        "source": "user_peaklist",
        "provenance": req.provenance,
        "params": {},
    }
    get_db().upsert_reference(ref, peaks)
    return {"saved": req.code, "n_peaks": len(peaks)}


@app.post("/api/references/cubic")
def create_cubic_reference(req: CustomCubicRequest):
    wl_a = wavelength_to_angstrom(req.wavelength, req.wavelength_unit)
    try:
        peaks = R.generate_cubic_pattern(
            req.structure, req.a_angstrom, wl_a, two_theta_max=req.two_theta_max
        )
    except (ValueError, KeyError) as e:
        raise HTTPException(422, f"无法生成立方参考谱：{e}")
    ref = {
        "code": req.code,
        "name": req.name,
        "structure": req.structure,
        "a_angstrom": req.a_angstrom,
        "wavelength_angstrom": wl_a,
        "source": "user_cubic",
        "provenance": req.provenance,
        "params": {"two_theta_max": req.two_theta_max},
    }
    get_db().upsert_reference(ref, peaks)
    return {"saved": req.code, "n_peaks": len(peaks), "peaks": peaks}


@app.delete("/api/references/{code}")
def delete_reference(code: str):
    bundle = get_db().get_reference_with_peaks(code)
    if bundle and bundle["reference"].get("source") == "builtin_synthetic":
        raise HTTPException(403, "内置教学参考谱不可删除（如需停用可在分析时不选它）")
    ok = get_db().delete_reference(code)
    if not ok:
        raise HTTPException(404, f"参考条目 {code} 不存在")
    return {"deleted": code}


# --------------------------------------------------------------------------
# 分析与演示
# --------------------------------------------------------------------------
@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    try:
        return analyze_from_request(req, get_db())
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.get("/api/demos")
def list_demos():
    return {"cases": constants()["demo_cases"]}


@app.post("/api/demos/generate")
def generate_demo(req: DemoRequest):
    db = get_db()
    ref_rows = {r["code"]: r for r in db.list_references()}
    peaks = {}
    for code, row in ref_rows.items():
        peaks[code] = db.get_reference_with_peaks(code)["peaks"]
    try:
        return build_demo_case(req.case, ref_rows, peaks)
    except ValueError as e:
        raise HTTPException(422, str(e))
