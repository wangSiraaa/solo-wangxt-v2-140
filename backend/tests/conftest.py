"""pytest 公共夹具：内存库 + TestClient（不依赖 Postgres 的 API 测试）。

真实 PostgreSQL 联调测试见 test_db_postgres.py，仅在设置 DATABASE_URL 时运行。
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture()
def client(monkeypatch):
    # 强制内存库，隔离 Postgres
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from app import db as db_module
    db_module._db = None  # 重新按无 DSN 初始化

    from fastapi.testclient import TestClient
    from app.main import app
    from app.seed import seed
    from app.db import get_db, reset_memory_store

    reset_memory_store()
    get_db().init_schema()
    seed(get_db())
    with TestClient(app) as c:
        yield c
    reset_memory_store()
    db_module._db = None
