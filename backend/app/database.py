"""SQLite 연결 설정.

두 사람이 같은 순간에 예약해도 중복 저장되지 않게 하려고(SPEC 5장):
  1) WAL 모드 - 읽기와 쓰기가 서로 덜 막힌다.
  2) 모든 트랜잭션을 BEGIN IMMEDIATE 로 시작 - 쓰기 잠금을 먼저 잡아서
     "겹침 확인 -> INSERT" 사이에 다른 사람이 끼어들 수 없게 한다.
  3) busy_timeout - 잠겨 있으면 바로 실패하지 않고 잠시 기다린다.
연구실 규모(사용자 수십 명)에서는 이 방식이 가장 단순하고 안전하다.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_config


class Base(DeclarativeBase):
    pass


def _create_engine(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{db_path}",
        future=True,
        # pysqlite 가 트랜잭션을 마음대로 열고 닫지 않도록 끈다.
        # (아래 "begin" 이벤트에서 직접 BEGIN IMMEDIATE 를 건다)
        connect_args={"isolation_level": None, "timeout": 15},
    )

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_conn, _record):  # noqa: ANN001
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA busy_timeout=15000")
        cur.close()

    @event.listens_for(engine, "begin")
    def _on_begin(conn):  # noqa: ANN001
        conn.exec_driver_sql("BEGIN IMMEDIATE")

    return engine


engine = _create_engine(get_config().database_path)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    """FastAPI 의존성: 요청 하나당 DB 세션 하나."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
