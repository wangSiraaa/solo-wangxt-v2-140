"""FastAPI 接口测试（内存库，TestClient）。"""

import json


def test_health_and_references_seeded(client):
    h = client.get("/api/health").json()
    assert h["status"] == "ok"
    assert h["n_references"] >= 8
    assert h["paid_databases_accessed"] is False
    refs = client.get("/api/references").json()["references"]
    codes = {r["code"] for r in refs}
    assert {"SYN-CU-FCC", "SYN-FE-BCC", "SYN-SI-DIA"} <= codes
    # provenance 必须明确"非付费数据库"
    assert all("非 ICDD" in r["provenance"] for r in refs)


def test_constants_expose_units(client):
    c = client.get("/api/constants").json()
    assert "Cu_Ka1" in c["common_targets_angstrom"]
    assert "2theta_deg" in c["angle_units"]
    assert "nm" in c["wavelength_units"]


def _generate(client, case):
    return client.post("/api/demos/generate", json={"case": case}).json()


def _analyze(client, demo, overrides=None):
    body = {
        "two_theta": demo["spectrum"]["two_theta"],
        "intensity": demo["spectrum"]["intensity"],
        "wavelength": demo["wavelength"],
        "wavelength_unit": demo["wavelength_unit"],
    }
    body.update(demo["truth"]["suggested_params"])
    body.update(overrides or {})
    return client.post("/api/analyze", json=body).json()


def test_analyze_single_phase(client):
    demo = _generate(client, "single_clean")
    r = _analyze(client, demo)
    assert r["convention"]["wavelength_angstrom"] == 1.54056
    assert r["convention"]["input_angle_unit"] == "2theta_deg"
    top = r["matching"]["candidates"][0]
    assert top["reference_code"] == "SYN-CU-FCC"
    assert top["scores"]["hit_count"] == 4
    assert r["disclaimer"].startswith("本结果是教学用离线复核")


def test_analyze_shift_case_and_explicit_correction(client):
    demo = _generate(client, "systematic_shift")
    bad = _analyze(client, demo, {"zero_shift": 0.0})
    scan = next(x for x in bad["matching"]["shift_scan"]["per_reference"]
                if x["reference_code"] == "SYN-CU-FCC")
    assert scan["best_hits_under_scan"] > scan["hits_at_zero_shift"]
    good = _analyze(client, demo, {"zero_shift": 0.6})
    cu_bad = next(c for c in bad["matching"]["candidates"] if c["reference_code"] == "SYN-CU-FCC")
    cu_good = next(c for c in good["matching"]["candidates"] if c["reference_code"] == "SYN-CU-FCC")
    assert cu_good["scores"]["hit_count"] >= cu_bad["scores"]["hit_count"]


def test_analyze_broad_case(client):
    demo = _generate(client, "broad_peaks")
    r = _analyze(client, demo)
    assert len(r["peaks"]["rejected_broad"]) == 1
    rb = r["peaks"]["rejected_broad"][0]
    assert rb["fwhm_deg"] > 2.0
    assert "超过显式上限" in rb["reason"]


def test_analyze_unknown_peaks_listed(client):
    demo = _generate(client, "weak_unknown")
    r = _analyze(client, demo)
    unk = {round(p["two_theta"], 1) for p in r["unexplained_overall"]}
    assert {34.2, 57.6} <= unk


def test_csv_text_input_and_parallel_curves(client):
    demo = _generate(client, "single_clean")
    x, y = demo["spectrum"]["two_theta"], demo["spectrum"]["intensity"]
    # 每 5 个点抽一个，减小体积；带表头
    lines = ["2theta,intensity  # 示例表头"]
    lines += [f"{x[i]},{y[i]}" for i in range(0, len(x), 5)]
    body = {"spectrum_text": "\n".join(lines),
            "wavelength": 1.54056, "prominence_sigma": 5.0}
    r = client.post("/api/analyze", json=body).json()
    assert len(r["curves"]["raw_intensity"]) == len(lines) - 1
    assert len(r["curves"]["background"]) == len(lines) - 1
    assert r["matching"]["candidates"][0]["reference_code"] == "SYN-CU-FCC"


def test_bad_wavelength_and_missing_data_rejected(client):
    resp = client.post("/api/analyze", json={"wavelength": -1, "spectrum_text": "1,1\n2,2\n3,3\n4,4\n5,5"})
    assert resp.status_code == 422
    resp = client.post("/api/analyze", json={"wavelength": 1.54})
    assert resp.status_code == 422


def test_custom_peaklist_reference_roundtrip(client):
    body = {
        "code": "USR-MY1", "name": "自制峰表", "wavelength": 1.54056,
        "provenance": "课堂自制：从开放教材图读取，精度有限",
        "peaks": [
            {"two_theta": 35.0, "intensity_rel": 80, "hkl": "x1"},
            {"two_theta": 60.0, "intensity_rel": 100, "hkl": "x2"},
        ],
    }
    assert client.post("/api/references/peaklist", json=body).status_code == 200
    got = client.get("/api/references/USR-MY1").json()
    assert got["reference"]["source"] == "user_peaklist"
    assert [p["two_theta"] for p in got["peaks"]] == [35.0, 60.0]
    assert client.delete("/api/references/USR-MY1").status_code == 200


def test_builtin_reference_not_deletable(client):
    assert client.delete("/api/references/SYN-CU-FCC").status_code == 403


def test_custom_cubic_reference(client):
    body = {
        "code": "USR-AU", "name": "金 Au FCC 自制立方", "structure": "FCC",
        "a_angstrom": 4.0782, "wavelength": 1.54056,
        "provenance": "用公开晶格常数合成的教学谱",
    }
    r = client.post("/api/references/cubic", json=body).json()
    assert r["n_peaks"] >= 3
    assert r["peaks"][0]["hkl"] == "(111)"
