"""种子参考数据：教科书常见 d-I 值（教学示例，非付费数据库内容，不用于真实鉴定）。

数值取自公开教科书/讲义中广泛转载的标准卡片值，仅作课程演示。
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from .models import Base, ReferencePattern, ReferencePeak
from .database import engine

SEED_DATA: list[dict] = [
    {
        "name": "Quartz (α-SiO2)", "formula": "SiO2",
        "source": "textbook values, teaching example",
        "note": "常见 α-石英主峰，d 单位 Å",
        "peaks": [(4.255, 20), (3.343, 100), (2.458, 8), (2.282, 8), (2.237, 4),
                  (2.128, 6), (1.980, 3), (1.817, 14), (1.672, 4), (1.659, 5),
                  (1.608, 3), (1.541, 9), (1.453, 6), (1.382, 8), (1.375, 6)],
    },
    {
        "name": "Corundum (α-Al2O3)", "formula": "Al2O3",
        "source": "textbook values, teaching example",
        "note": "刚玉主峰",
        "peaks": [(3.479, 75), (2.552, 90), (2.379, 40), (2.165, 3), (2.085, 100),
                  (1.740, 45), (1.601, 80), (1.546, 4), (1.514, 30), (1.510, 6),
                  (1.404, 30), (1.374, 50), (1.337, 2), (1.239, 16), (1.234, 8)],
    },
    {
        "name": "Halite (NaCl)", "formula": "NaCl",
        "source": "textbook values, teaching example",
        "note": "石盐主峰",
        "peaks": [(3.258, 13), (2.821, 100), (1.994, 55), (1.701, 15), (1.628, 11),
                  (1.410, 6), (1.294, 13), (1.261, 10), (1.1515, 7), (1.0855, 2),
                  (0.9969, 4)],
    },
    {
        "name": "Silicon (Si)", "formula": "Si",
        "source": "textbook values, teaching example",
        "note": "常用标样",
        "peaks": [(3.1355, 100), (1.9201, 55), (1.6375, 30), (1.3577, 6),
                  (1.2460, 11), (1.1086, 12), (1.0452, 6), (0.9600, 3),
                  (0.9180, 7), (0.8587, 8)],
    },
    {
        "name": "Calcite (CaCO3)", "formula": "CaCO3",
        "source": "textbook values, teaching example",
        "note": "方解石主峰",
        "peaks": [(3.857, 12), (3.035, 100), (2.845, 3), (2.495, 14), (2.285, 18),
                  (2.095, 18), (1.913, 17), (1.875, 17), (1.626, 4), (1.604, 5),
                  (1.587, 5), (1.525, 3)],
    },
    {
        "name": "Fluorite (CaF2)", "formula": "CaF2",
        "source": "textbook values, teaching example",
        "note": "萤石主峰",
        "peaks": [(3.154, 93), (1.932, 100), (1.647, 53), (1.366, 9), (1.253, 12),
                  (1.115, 11), (1.0515, 31), (0.966, 4), (0.923, 9), (0.863, 10)],
    },
]


def init_db() -> None:
    Base.metadata.create_all(engine)


def seed_if_empty(db: Session) -> int:
    if db.query(ReferencePattern).count() > 0:
        return 0
    n = 0
    for entry in SEED_DATA:
        pat = ReferencePattern(name=entry["name"], formula=entry["formula"],
                               source=entry["source"], note=entry["note"])
        pat.peaks = [ReferencePeak(d_angstrom=d, intensity_rel=i)
                     for d, i in entry["peaks"]]
        db.add(pat)
        n += 1
    db.commit()
    return n
