"""开放/自制参考谱：立方晶系合成衍射条目。

这些参考条目不来自 ICDD/PDF 等付费数据库，而是由教科书级晶体学参数
（晶格常数、空间点阵消光规则、原子散射因子近似、洛伦兹-偏振因子）
**合成**得到的教学参考谱。每条参考都带 provenance 字段注明其来源与
近似程度，供课堂复核使用，不能替代真实标准卡片。

强度模型（多晶粉末，θ-2θ，未计德拜-沃勒因子与多重性以外的织构）：
    I(hkl) ∝ M * |F|^2 * LP(θ)
    LP(θ) = (1 + cos²(2θ)) / (sin²θ cosθ)        （未偏振入射光）
原子散射因子使用常数近似 f ≈ 原子序数的经验折算（教学近似，sinθ/λ 依赖被忽略），
因此相对强度是粗略的；峰**位置**由晶格常数与布拉格定律严格给出，不受影响。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .units import bragg_two_theta_deg

# 常见靶材波长（Å），仅作为前端可选项的说明，不作为隐藏默认
COMMON_TARGETS = {
    "Cu_Ka1": 1.54056,
    "Cu_Ka": 1.54184,   # Kα1/Kα2 加权平均
    "Mo_Ka1": 0.70930,
    "Co_Ka1": 1.78897,
    "Fe_Ka1": 1.93604,
    "Cr_Ka1": 2.28970,
}


@dataclass
class Atom:
    """晶胞内原子：元素、近似散射因子常数（教学近似）、分数坐标。"""

    element: str
    f: float
    x: float
    y: float
    z: float


def _structure_factor(structure: str, h: int, k: int, l: int, atoms: list[Atom]) -> float:
    """按点阵类型消光规则 + 基元原子求和，返回 |F|。"""
    s = h + k + l

    if structure == "SC":                      # 简单立方，无系统消光
        basis_ok = True
    elif structure == "BCC":
        basis_ok = (s % 2 == 0)
    elif structure == "FCC":
        basis_ok = all(v % 2 == (h % 2) for v in (k, l))  # h,k,l 全奇或全偶
    elif structure == "DIAMOND":
        if not all(v % 2 == (h % 2) for v in (k, l)):
            basis_ok = False                       # FCC 消光
        elif all(v % 2 == 1 for v in (h, k, l)):
            basis_ok = True                        # 全奇
        else:
            basis_ok = (s % 4 != 2)                # 全偶且 h+k+l ≠ 4n+2
    elif structure == "NACL":
        # Na(0,0,0)+FCC 与 Cl(1/2,0,0)+FCC：
        # 全奇: F=4(f_Na-f_Cl)；全偶: F=4(f_Na+f_Cl)
        basis_ok = all(v % 2 == (h % 2) for v in (k, l))
    elif structure == "CSCL":
        basis_ok = True                            # 基元给出权重，无完全消光
    elif structure == "FLUORITE":
        # CaF2：Ca 在 FCC 位，F 在 (1/4,1/4,1/4)+ 四面体位（8 个）
        basis_ok = True
    else:
        raise ValueError(f"未知结构类型 {structure!r}")

    if not basis_ok:
        return 0.0

    def dot(h, k, l, a: Atom) -> float:
        return h * a.x + k * a.y + l * a.z

    if structure in ("SC", "BCC", "FCC", "DIAMOND"):
        # atoms 为单原子基元（DIAMOND 基元两个同位原子）
        f_total = sum(a.f * math.cos(2 * math.pi * dot(h, k, l, a)) for a in atoms)
        return abs(f_total)

    if structure == "NACL":
        f_na = atoms[0].f
        f_cl = atoms[1].f
        return abs(4.0 * (f_na - f_cl)) if s % 2 == 1 else abs(4.0 * (f_na + f_cl))

    if structure == "CSCL":
        f_cs, f_cl = atoms[0].f, atoms[1].f
        return abs(f_cs + f_cl * ((-1) ** s))

    if structure == "FLUORITE":
        f_ca, f_f = atoms[0].f, atoms[1].f
        ca = f_ca * (1 + (-1) ** (h + k) + (-1) ** (h + l) + (-1) ** (k + l))
        f_sites = [
            (1, 1, 1), (1, 3, 3), (3, 1, 3), (3, 3, 1),
            (3, 3, 3), (3, 1, 1), (1, 3, 1), (1, 1, 3),
        ]
        fluorite = f_f * sum(
            math.cos((math.pi / 2.0) * (h * a + k * b + l * c)) for a, b, c in f_sites
        )
        return abs(ca + fluorite)

    raise ValueError(structure)


def _multiplicity(h: int, k: int, l: int) -> int:
    """立方晶系等效晶面族 {hkl} 的多重性因子（每个多重集只分类一次）。"""
    vals = sorted((abs(h), abs(k), abs(l)))
    nonzero = sum(1 for v in vals if v != 0)
    if nonzero == 3:
        return {1: 8, 2: 24, 3: 48}[len(set(vals))]   # {hhh}=8 {hhl}=24 {hkl}=48
    if nonzero == 2:
        return 12 if vals[1] == vals[2] else 24       # {0kk}=12 {0kl}=24
    return 6                                          # {00l}=6


def _lp_factor(theta_rad: float) -> float:
    s, c = math.sin(theta_rad), math.cos(theta_rad)
    two_theta = 2 * theta_rad
    return (1.0 + math.cos(two_theta) ** 2) / (s * s * c)


def _default_atoms(structure: str) -> list[Atom]:
    table = {
        "SC": [Atom("Po", 8.0, 0, 0, 0)],
        "BCC": [Atom("Fe", 14.0, 0, 0, 0)],          # f 为教学常数近似
        "FCC": [Atom("Cu", 17.0, 0, 0, 0)],
        "DIAMOND": [Atom("Si", 10.0, 0, 0, 0), Atom("Si", 10.0, 0.25, 0.25, 0.25)],
        "NACL": [Atom("Na", 7.0, 0, 0, 0), Atom("Cl", 13.0, 0.5, 0, 0)],
        "CSCL": [Atom("Cs", 30.0, 0, 0, 0), Atom("Cl", 13.0, 0.5, 0.5, 0.5)],
        "FLUORITE": [Atom("Ca", 14.0, 0, 0, 0), Atom("F", 6.0, 0.25, 0.25, 0.25)],
    }
    return table[structure]


def _canonical_hkl(h: int, k: int, l: int) -> str:
    """规范的 {hkl} 标注：非零指数降序、零放最后。如 (0,2,0)->(200)，(0,1,1)->(110)。"""
    vals = sorted((h, k, l), key=lambda v: (v == 0, -v))
    return "(" + "".join(str(v) for v in vals) + ")"


def generate_cubic_pattern(
    structure: str,
    a_angstrom: float,
    wavelength_angstrom: float,
    *,
    atoms: list[Atom] | None = None,
    two_theta_max: float = 90.0,
    relative_intensity_floor: float = 0.0,
) -> list[dict]:
    """生成立方相的合成参考峰表：[{hkl, d, two_theta, intensity_rel, multiplicity}]。

    相对强度归一到最强峰 = 100。**强度归一不改变任何峰位。**
    """
    if atoms is None:
        atoms = _default_atoms(structure)

    n_max = int(math.ceil(math.sqrt((2.0 * a_angstrom / wavelength_angstrom) ** 2 * 3))) + 1
    rows: list[dict] = []
    for h in range(n_max + 1):
        for k in range(h, n_max + 1):
            for l in range(k, n_max + 1):
                if h == k == l == 0:
                    continue
                n2 = h * h + k * k + l * l
                d = a_angstrom / math.sqrt(n2)
                ratio = wavelength_angstrom / (2.0 * d)
                if ratio > 1.0:
                    continue
                f_mod = _structure_factor(structure, h, k, l, atoms)
                if f_mod == 0.0:
                    continue
                tt = bragg_two_theta_deg(d, wavelength_angstrom)
                if tt > two_theta_max:
                    continue
                theta = math.radians(tt / 2.0)
                m = _multiplicity(h, k, l)
                intensity = m * f_mod * f_mod * _lp_factor(theta)
                rows.append(
                    {
                        "hkl": _canonical_hkl(h, k, l),
                        "d_angstrom": round(d, 5),
                        "two_theta": round(tt, 4),
                        "_raw_intensity": intensity,
                        "multiplicity": m,
                    }
                )

    rows.sort(key=lambda r: r["two_theta"])
    imax = max((r["_raw_intensity"] for r in rows), default=1.0)
    out = []
    for r in rows:
        rel = 100.0 * r["_raw_intensity"] / imax
        if rel < relative_intensity_floor:
            continue
        out.append(
            {
                "hkl": r["hkl"],
                "d_angstrom": r["d_angstrom"],
                "two_theta": r["two_theta"],
                "intensity_rel": round(rel, 2),
                "multiplicity": r["multiplicity"],
            }
        )
    return out


# ---------------------------------------------------------------------------
# 内置教学参考条目（晶格常数为室温近似值，波长随条目固定并显式记录）
# 这些是自制/开放教学数据，不访问任何付费数据库。
# ---------------------------------------------------------------------------
BUILTIN_REFERENCES = [
    {
        "code": "SYN-CU-FCC",
        "name": "铜 Cu（合成，FCC 教学谱）",
        "structure": "FCC",
        "a_angstrom": 3.6149,
        "wavelength_angstrom": COMMON_TARGETS["Cu_Ka1"],
        "provenance": "由 a=3.6149 Å、FCC 消光、M|F|²LP 模型合成；f 为常数近似。非 ICDD 数据。",
    },
    {
        "code": "SYN-FE-BCC",
        "name": "α-铁 Fe（合成，BCC 教学谱）",
        "structure": "BCC",
        "a_angstrom": 2.8665,
        "wavelength_angstrom": COMMON_TARGETS["Cu_Ka1"],
        "provenance": "由 a=2.8665 Å、BCC 消光、M|F|²LP 模型合成。非 ICDD 数据。",
    },
    {
        "code": "SYN-AL-FCC",
        "name": "铝 Al（合成，FCC 教学谱）",
        "structure": "FCC",
        "a_angstrom": 4.0495,
        "wavelength_angstrom": COMMON_TARGETS["Cu_Ka1"],
        "provenance": "由 a=4.0495 Å、FCC 消光、M|F|²LP 模型合成。非 ICDD 数据。",
    },
    {
        "code": "SYN-NI-FCC",
        "name": "镍 Ni（合成，FCC 教学谱）",
        "structure": "FCC",
        "a_angstrom": 3.5240,
        "wavelength_angstrom": COMMON_TARGETS["Cu_Ka1"],
        "provenance": "由 a=3.5240 Å、FCC 消光、M|F|²LP 模型合成。非 ICDD 数据。",
    },
    {
        "code": "SYN-SI-DIA",
        "name": "硅 Si（合成，金刚石立方教学谱）",
        "structure": "DIAMOND",
        "a_angstrom": 5.4310,
        "wavelength_angstrom": COMMON_TARGETS["Cu_Ka1"],
        "provenance": "由 a=5.4310 Å、金刚石消光、M|F|²LP 模型合成。非 ICDD 数据。",
    },
    {
        "code": "SYN-NACL",
        "name": "氯化钠 NaCl（合成，岩盐结构教学谱）",
        "structure": "NACL",
        "a_angstrom": 5.6402,
        "wavelength_angstrom": COMMON_TARGETS["Cu_Ka1"],
        "provenance": "由 a=5.6402 Å、岩盐消光、M|F|²LP 模型合成。非 ICDD 数据。",
    },
    {
        "code": "SYN-CSCL",
        "name": "氯化铯 CsCl（合成，CsCl 型教学谱）",
        "structure": "CSCL",
        "a_angstrom": 4.1230,
        "wavelength_angstrom": COMMON_TARGETS["Cu_Ka1"],
        "provenance": "由 a=4.1230 Å、CsCl 基元、M|F|²LP 模型合成。非 ICDD 数据。",
    },
    {
        "code": "SYN-CAF2",
        "name": "氟化钙 CaF₂（合成，萤石结构教学谱）",
        "structure": "FLUORITE",
        "a_angstrom": 5.4630,
        "wavelength_angstrom": COMMON_TARGETS["Cu_Ka1"],
        "provenance": "由 a=5.4630 Å、萤石基元、M|F|²LP 模型合成。非 ICDD 数据。",
    },
]


def build_builtin_peak_rows(ref: dict, two_theta_max: float = 90.0) -> list[dict]:
    return generate_cubic_pattern(
        ref["structure"],
        ref["a_angstrom"],
        ref["wavelength_angstrom"],
        two_theta_max=two_theta_max,
    )
