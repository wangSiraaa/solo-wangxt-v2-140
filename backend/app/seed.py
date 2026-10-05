"""把内置开放/自制教学参考谱幂等地写入 PostgreSQL（或内存库）。

用法：
    DATABASE_URL=postgresql://xrd@localhost:55432/xrdbench python3 -m app.seed
"""

from __future__ import annotations

from .db import get_db
from .xrd import references as R


def seed(db=None) -> int:
    db = db or get_db()
    db.init_schema()
    n = 0
    for ref_def in R.BUILTIN_REFERENCES:
        peaks = R.build_builtin_peak_rows(ref_def)
        ref = {
            "code": ref_def["code"],
            "name": ref_def["name"],
            "structure": ref_def["structure"],
            "a_angstrom": ref_def["a_angstrom"],
            "wavelength_angstrom": ref_def["wavelength_angstrom"],
            "source": "builtin_synthetic",
            "provenance": ref_def["provenance"],
            "params": {"two_theta_max": 90.0, "intensity_model": "M|F|^2 LP, f 为常数近似"},
        }
        db.upsert_reference(ref, peaks)
        n += 1
    return n


if __name__ == "__main__":  # pragma: no cover
    inserted = seed()
    total = get_db().count_references()
    print(f"内置参考谱已同步：{inserted} 条；库内共 {total} 条")
