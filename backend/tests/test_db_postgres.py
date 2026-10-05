"""真实 PostgreSQL 联调测试。

仅当环境变量 DATABASE_URL 已配置且可连通时运行，否则整体跳过。
运行（见仓库根 README）：
    export DATABASE_URL="postgresql://xrd@/xrdbench?host=/tmp&port=55432"
    pytest tests/test_db_postgres.py
"""

import os

import psycopg
import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="未设置 DATABASE_URL，跳过真实 Postgres 测试"
)


@pytest.fixture()
def pg_db():
    from app import db as db_module
    dsn = os.environ["DATABASE_URL"]
    try:
        with psycopg.connect(dsn) as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("DROP TABLE IF EXISTS reference_peaks, analysis_runs, reference_entries CASCADE")
    except psycopg.OperationalError:
        pytest.skip("PostgreSQL 不可达")
    db_module._db = None
    from app.db import get_db, reset_memory_store
    reset_memory_store()
    db = get_db()
    db.init_schema()
    from app.seed import seed
    n = seed(db)
    yield db, n
    db_module._db = None


def test_schema_seed_and_counts(pg_db):
    db, n = pg_db
    assert n == 8
    assert db.count_references() == 8
    bundle = db.get_reference_with_peaks("SYN-CU-FCC")
    assert bundle is not None
    assert len(bundle["peaks"]) >= 3
    # 表结构确实来自 Postgres
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_name IN ('reference_entries','reference_peaks','analysis_runs')"
            )
            assert len(cur.fetchall()) == 3


def test_upsert_is_idempotent(pg_db):
    db, _ = pg_db
    from app.seed import seed
    seed(db)
    assert db.count_references() == 8
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM reference_peaks WHERE reference_code='SYN-CU-FCC'")
            first = cur.fetchone()[0]
    seed(db)
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM reference_peaks WHERE reference_code='SYN-CU-FCC'")
            assert cur.fetchone()[0] == first  # 没有重复写入


def test_user_reference_persists_and_analysis_run_saved(pg_db):
    db, _ = pg_db
    db.upsert_reference(
        {
            "code": "USR-PG1", "name": "PG 自制", "structure": "CUSTOM",
            "a_angstrom": None, "wavelength_angstrom": 1.54056,
            "source": "user_peaklist", "provenance": "PG 联调自制", "params": {},
        },
        [{"two_theta": 30.0, "intensity_rel": 100, "hkl": "(100)"}],
    )
    assert db.get_reference_with_peaks("USR-PG1")["peaks"][0]["two_theta"] == 30.0
    rid = db.save_run("联调留档", {"k": 1}, {"ok": True})
    assert isinstance(rid, int) and rid > 0
    # 自清理，避免测试残留污染课堂库
    db.delete_reference("USR-PG1")
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM analysis_runs WHERE label='联调留档'")
