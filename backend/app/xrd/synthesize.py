"""教学用合成谱生成：用于"单相、系统偏移、宽峰、混合"等自检测试用例。

所有谱均由已知参考峰表 + 显式生成参数（展宽、噪声、背景、偏移）合成，
truth（真实物相与注入参数）随谱返回，便于核对复核台自身的表现。
"""

from __future__ import annotations

import numpy as np


def _pseudo_voigt(x, center, amplitude, fwhm, eta: float = 0.0):
    sigma = fwhm / (2.0 * np.sqrt(2.0 * np.log(2.0)))
    gamma = fwhm / 2.0
    g = amplitude * np.exp(-0.5 * ((x - center) / sigma) ** 2)
    l = amplitude / (1.0 + ((x - center) / gamma) ** 2)
    return eta * l + (1.0 - eta) * g


def synthesize_pattern(
    peak_rows: list[dict],
    *,
    x_min: float = 15.0,
    x_max: float = 90.0,
    step: float = 0.02,
    peak_fwhm_deg: float = 0.12,
    instrument_fwhm_deg: float = 0.08,
    zero_shift: float = 0.0,
    intensity_scale: float = 1000.0,
    noise_sigma: float = 8.0,
    background_level: float = 60.0,
    background_slope: float = -0.4,
    broad_humps: list[dict] | None = None,
    eta: float = 0.0,
    seed: int = 1,
    intensity_key: str = "intensity_rel",
) -> dict:
    """从峰表合成一张含背景/噪声/偏移的"实测"谱。

    zero_shift 注入到角轴读数里（仪器读数 = 真实 + shift），
    以模拟仪器零点误差；样本总宽化 peak_fwhm_deg 与仪器展宽分开给出。
    broad_humps: [{center, amplitude, fwhm}] 注入无定形宽鼓包。
    """
    rng = np.random.default_rng(seed)
    x = np.arange(x_min, x_max + 0.5 * step, step)
    y = background_level + background_slope * (x - x_min)

    for row in peak_rows:
        amp = intensity_scale * (row[intensity_key] / 100.0)
        center = row["two_theta"] + zero_shift
        if x_min <= center <= x_max:
            y += _pseudo_voigt(x, center, amp, peak_fwhm_deg, eta)

    if broad_humps:
        for h in broad_humps:
            y += _pseudo_voigt(
                x, h["center"] + zero_shift, h["amplitude"], h["fwhm"], eta=0.0
            )

    y = np.maximum(y + rng.normal(0.0, noise_sigma, size=x.size), 0.0)
    return {
        "two_theta": np.round(x, 4).tolist(),
        "intensity": np.round(y, 3).tolist(),
    }


# ---------------------------------------------------------------------------
# 自检测试用例（truth 与生成参数显式记录，不参与分析，仅供核对）
# ---------------------------------------------------------------------------
def build_demo_case(case: str, references: dict | list, peaks: dict[str, list[dict]]) -> dict:
    from .references import COMMON_TARGETS
    cu = peaks["SYN-CU-FCC"]
    fe = peaks["SYN-FE-BCC"]
    si = peaks["SYN-SI-DIA"]
    al = peaks["SYN-AL-FCC"]

    if case == "single_clean":
        spec = synthesize_pattern(
            cu, peak_fwhm_deg=0.12, instrument_fwhm_deg=0.08,
            noise_sigma=6.0, seed=11,
        )
        truth = {
            "case": "single_clean",
            "title": "单相合成谱：Cu（FCC），无偏移、窄峰",
            "phases": ["SYN-CU-FCC"],
            "zero_shift_deg": 0.0,
            "expected_behaviour": "Cu 候选应居首；Fe/Si 等应仅少量偶然命中或不达标。",
            "suggested_params": {
                "zero_shift": 0.0, "tolerance_deg": 0.15, "instrument_fwhm_deg": 0.08,
                "max_fwhm_deg": 3.0, "prominence_sigma": 5.0,
            },
        }
    elif case == "systematic_shift":
        spec = synthesize_pattern(
            cu, peak_fwhm_deg=0.12, instrument_fwhm_deg=0.08,
            zero_shift=0.60, noise_sigma=6.0, seed=23,
        )
        truth = {
            "case": "systematic_shift",
            "title": "系统偏移谱：Cu + 注入 +0.60° 零点偏移",
            "phases": ["SYN-CU-FCC"],
            "zero_shift_deg": 0.60,
            "expected_behaviour": (
                "zero_shift=0 时 Cu 命中显著下降，shift_diagnostic 应提示约 +0.60°；"
                "显式填入 0.60 重算后命中恢复。"
            ),
            "suggested_params": {
                "zero_shift": 0.60, "tolerance_deg": 0.15, "instrument_fwhm_deg": 0.08,
                "max_fwhm_deg": 3.0, "prominence_sigma": 5.0,
            },
        }
    elif case == "broad_peaks":
        spec = synthesize_pattern(
            si,
            peak_fwhm_deg=0.9, instrument_fwhm_deg=0.08,
            noise_sigma=8.0, seed=37,
            broad_humps=[{"center": 23.0, "amplitude": 800.0, "fwhm": 4.0}],
        )
        truth = {
            "case": "broad_peaks",
            "title": "宽峰案例：Si 宽化峰 + 一个无定形宽鼓包（约 23°，FWHM≈4°）",
            "phases": ["SYN-SI-DIA"],
            "zero_shift_deg": 0.0,
            "amorphous_humps": [{"center_deg": 23.0, "fwhm_deg": 4.0}],
            "expected_behaviour": (
                "宽鼓包残峰（约 23.4°，FWHM≈2.3°，大于 max_fwhm_deg=2.0）应出现在 "
                "rejected_broad；Si 宽峰（实测 FWHM≈0.6–0.9°）在放宽 max_fwhm_deg 后"
                "参与匹配，其 intrinsic_fwhm 应明显大于仪器展宽 0.08°。"
            ),
            "suggested_params": {
                "zero_shift": 0.0, "tolerance_deg": 0.35, "instrument_fwhm_deg": 0.08,
                "max_fwhm_deg": 2.0, "prominence_sigma": 5.0, "bg_window": 40,
            },
        }
    elif case == "mixture":
        rows = cu + fe
        rows = sorted(rows, key=lambda r: r["two_theta"])
        # 让 Fe 弱一些，模拟第二相含量较低
        fe_weaker = [
            {**r, "intensity_rel": r["intensity_rel"] * 0.45}
            for r in fe
        ]
        spec = synthesize_pattern(
            cu + fe_weaker, peak_fwhm_deg=0.13, instrument_fwhm_deg=0.08,
            noise_sigma=7.0, seed=51,
        )
        truth = {
            "case": "mixture",
            "title": "两相混合：Cu（主相）+ α-Fe（弱第二相，强度×0.45）",
            "phases": ["SYN-CU-FCC", "SYN-FE-BCC"],
            "zero_shift_deg": 0.0,
            "expected_behaviour": (
                "Cu 与 Fe 都应通过最小命中数；Fe 候选解释的是 Cu 解释不了的"
                "那几个未知峰（约 44.7° 附近两峰相邻需关注），不产生唯一结论。"
            ),
            "suggested_params": {
                "zero_shift": 0.0, "tolerance_deg": 0.15, "instrument_fwhm_deg": 0.08,
                "max_fwhm_deg": 3.0, "prominence_sigma": 5.0,
            },
        }
    elif case == "weak_unknown":
        # Al 主相 + 两个不属于任何内置参考的"杂质"未知峰
        spec = synthesize_pattern(
            al, peak_fwhm_deg=0.12, instrument_fwhm_deg=0.08,
            noise_sigma=6.0, seed=67,
        )
        x = np.array(spec["two_theta"])
        y = np.array(spec["intensity"])
        for center, amp in ((34.2, 180.0), (57.6, 120.0)):
            y += _pseudo_voigt(x, center, amp, 0.14)
        spec = {"two_theta": x.tolist(), "intensity": np.round(y, 3).tolist()}
        truth = {
            "case": "weak_unknown",
            "title": "主相 Al + 两个未知杂质峰（34.2°、57.6°）",
            "phases": ["SYN-AL-FCC"],
            "unknown_injected_peaks": [34.2, 57.6],
            "zero_shift_deg": 0.0,
            "expected_behaviour": (
                "Al 应居首，但 34.2° 与 57.6° 必须作为 unknown_sample_peaks 列出，"
                "不能被最佳候选吸收成'已鉴定'。"
            ),
            "suggested_params": {
                "zero_shift": 0.0, "tolerance_deg": 0.15, "instrument_fwhm_deg": 0.08,
                "max_fwhm_deg": 3.0, "prominence_sigma": 5.0,
            },
        }
    else:
        raise ValueError(f"未知测试用例 {case!r}")

    return {
        "case": truth["case"],
        "title": truth["title"],
        "angle_unit": "2theta_deg",
        "wavelength": COMMON_TARGETS["Cu_Ka1"],
        "wavelength_unit": "angstrom",
        "spectrum": spec,
        "truth": truth,
        "note": "合成教学数据：truth 仅供教师核对，分析接口不读取 truth。",
    }
