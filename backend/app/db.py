"""PostgreSQL 访问层（psycopg3）。

DATABASE_URL 指向真实 Postgres。为方便纯算法离线测试，当未配置 DATABASE_URL
时自动退化为内存库（仅供测试与课堂演示单机模式，生产/联调使用 Postgres）。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

try:
    import psycopg
except ImportError:  # pragma: no cover
    psycopg = None

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema.sql"

_memory_store: dict[str, dict] = {}


class DB:
    def __init__(self, dsn: str | None):
        self.dsn = dsn
        self.memory = dsn is None
        if not self.memory and psycopg is None:
            raise RuntimeError("未安装 psycopg，无法连接 PostgreSQL")

    def connect(self):
        if self.memory:
            return None
        return psycopg.connect(self.dsn, autocommit=True)

    def init_schema(self) -> None:
        if self.memory:
            return
        sql = SCHEMA_PATH.read_text(encoding="utf-8")
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)

    # -- references --------------------------------------------------------
    def upsert_reference(self, ref: dict, peaks: list[dict]) -> None:
        if self.memory:
            _memory_store[ref["code"]] = {"reference": ref, "peaks": peaks}
            return
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO reference_entries
                        (code, name, structure, a_angstrom, wavelength_angstrom,
                         source, provenance, params_json)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (code) DO UPDATE SET
                        name=EXCLUDED.name,
                        structure=EXCLUDED.structure,
                        a_angstrom=EXCLUDED.a_angstrom,
                        wavelength_angstrom=EXCLUDED.wavelength_angstrom,
                        source=EXCLUDED.source,
                        provenance=EXCLUDED.provenance,
                        params_json=EXCLUDED.params_json
                    """,
                    (
                        ref["code"], ref["name"], ref.get("structure"),
                        ref.get("a_angstrom"), ref["wavelength_angstrom"],
                        ref.get("source", "user_peaklist"), ref["provenance"],
                        json.dumps(ref.get("params", {}), ensure_ascii=False),
                    ),
                )
                cur.execute("DELETE FROM reference_peaks WHERE reference_code=%s", (ref["code"],))
                cur.executemany(
                    """
                    INSERT INTO reference_peaks
                        (reference_code, two_theta, intensity_rel, hkl, d_angstrom,
                         multiplicity, ord)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                    """,
                    [
                        (
                            ref["code"], p["two_theta"], p.get("intensity_rel", 0),
                            p.get("hkl"), p.get("d_angstrom"), p.get("multiplicity"), i,
                        )
                        for i, p in enumerate(peaks)
                    ],
                )

    def list_references(self) -> list[dict]:
        if self.memory:
            return [_row_ref(v["reference"]) for v in _memory_store.values()]
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT code, name, structure, a_angstrom, wavelength_angstrom,
                              source, provenance, params_json
                       FROM reference_entries ORDER BY code"""
                )
                return [_row_ref(r) for r in cur.fetchall()]

    def get_reference_with_peaks(self, code: str) -> dict | None:
        if self.memory:
            v = _memory_store.get(code)
            return None if v is None else {"reference": _row_ref(v["reference"]), "peaks": v["peaks"]}
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT code, name, structure, a_angstrom, wavelength_angstrom,
                              source, provenance, params_json
                       FROM reference_entries WHERE code=%s""",
                    (code,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                cur.execute(
                    """SELECT two_theta, intensity_rel, hkl, d_angstrom, multiplicity
                       FROM reference_peaks WHERE reference_code=%s ORDER BY ord""",
                    (code,),
                )
                peaks = [
                    {
                        "two_theta": r[0], "intensity_rel": r[1], "hkl": r[2],
                        "d_angstrom": r[3], "multiplicity": r[4],
                    }
                    for r in cur.fetchall()
                ]
                return {"reference": _row_ref(row), "peaks": peaks}

    def delete_reference(self, code: str) -> bool:
        if self.memory:
            return _memory_store.pop(code, None) is not None
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM reference_entries WHERE code=%s", (code,))
                return cur.rowcount > 0

    def count_references(self) -> int:
        if self.memory:
            return len(_memory_store)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM reference_entries")
                return cur.fetchone()[0]

    # -- analysis archive --------------------------------------------------
    def save_run(self, label: str | None, request_obj: dict, result_obj: dict) -> int:
        if self.memory:
            return 0
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO analysis_runs (label, request_json, result_json) "
                    "VALUES (%s,%s,%s) RETURNING id",
                    (label, json.dumps(request_obj, ensure_ascii=False),
                     json.dumps(result_obj, ensure_ascii=False)),
                )
                return cur.fetchone()[0]


def _row_ref(row: Any) -> dict:
    if isinstance(row, dict):
        return row
    code, name, structure, a, wl, source, provenance, params = row
    return {
        "code": code,
        "name": name,
        "structure": structure,
        "a_angstrom": a,
        "wavelength_angstrom": wl,
        "source": source,
        "provenance": provenance,
        "params": params if isinstance(params, dict) else json.loads(params or "{}"),
    }


def get_dsn() -> str | None:
    return os.environ.get("DATABASE_URL") or None


_db: DB | None = None


def get_db() -> DB:
    global _db
    if _db is None:
        _db = DB(get_dsn())
    return _db


def reset_memory_store() -> None:
    """仅供测试：清空内存库。"""
    _memory_store.clear()
