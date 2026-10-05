"""数据库连接。默认 PostgreSQL；测试可用 DATABASE_URL=sqlite:///... 覆盖。"""
from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://xrd:xrd@db:5432/xrd",
)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine_kwargs: dict = {"connect_args": connect_args}
if ":memory:" in DATABASE_URL:
    # 内存 SQLite：全连接共享同一库，否则测试里表会丢
    from sqlalchemy.pool import StaticPool
    engine_kwargs["poolclass"] = StaticPool
engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
