"""DB 연결 설정. SQLite(파일 하나)와 Postgres(Neon 등) 두 가지를 모두 지원한다.

어떤 DB를 쓸지는 **환경변수 `DATABASE_URL` 하나로 결정한다.**
  - `DATABASE_URL` 이 있으면  -> 그 주소의 Postgres
  - 없으면                    -> 지금까지처럼 config 의 database_path 에 있는 SQLite 파일
`DATABASE_URL` 은 비밀값이므로 코드나 config.yaml 에 적지 않는다. 항상 환경변수로만 읽는다.

------------------------------------------------------------------
"같은 GPU에 시간이 겹치는 예약 금지"를 두 DB에서 각각 어떻게 지키나
------------------------------------------------------------------
두 사람이 같은 순간에 같은 시간을 신청해도 한 명만 성공해야 한다(SPEC 5장).
'겹침 확인 -> INSERT' 사이에 다른 사람이 끼어들 수 있기 때문에 DB의 도움이 필요하다.

* SQLite: 아래 세 가지 (이 파일에서 처리)
  1) WAL 모드 - 읽기와 쓰기가 서로 덜 막힌다.
  2) 모든 트랜잭션을 BEGIN IMMEDIATE 로 시작 - 쓰기 잠금을 먼저 잡아서
     "겹침 확인 -> INSERT" 사이에 다른 사람이 끼어들 수 없게 한다.
  3) busy_timeout - 잠겨 있으면 바로 실패하지 않고 잠시 기다린다.

* Postgres: BEGIN IMMEDIATE 같은 게 없다. 대신 **테이블 자체에 겹침 금지 제약**
  (EXCLUDE 제약)을 걸어서 DB가 직접 거부하게 한다.
  -> models.py 의 `ensure_overlap_constraint()` 참고.

그래서 아래 SQLite 전용 설정(connect_args, PRAGMA, BEGIN IMMEDIATE)은
**SQLite 일 때만** 걸어야 한다. Postgres 엔진에 걸면 오류가 난다.
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_config

#: Postgres 주소를 담는 환경변수 이름. (예: Neon 대시보드에서 복사한 연결 문자열)
DATABASE_URL_ENV = "DATABASE_URL"


class Base(DeclarativeBase):
    pass


def normalize_database_url(url: str) -> str:
    """DB 주소를 SQLAlchemy 가 이해하는 형태로 고친다.

    Neon 같은 서비스는 `postgres://...` 또는 `postgresql://...` 형태를 알려 주는데,
    SQLAlchemy 는 이걸 보면 기본 드라이버(psycopg2)를 찾는다.
    우리는 psycopg(3) 를 쓰므로 `postgresql+psycopg://` 로 바꿔 준다.
    이미 드라이버가 적혀 있으면(`postgresql+asyncpg://` 등) 건드리지 않는다.
    """
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


def _create_sqlite_engine(db_path: Path):
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


def _create_postgres_engine(url: str):
    return create_engine(
        normalize_database_url(url),
        future=True,
        # 클라우드 DB는 놀고 있는 연결을 끊어 버리는 일이 있다.
        # 쓰기 전에 살아 있는지 한 번 확인해서 "연결이 끊겼습니다" 오류를 막는다.
        pool_pre_ping=True,
    )


def _build_engine():
    """환경변수를 보고 Postgres 또는 SQLite 엔진을 만든다."""
    url = os.environ.get(DATABASE_URL_ENV, "").strip()
    if url:
        return _create_postgres_engine(url)
    return _create_sqlite_engine(get_config().database_path)


engine = _build_engine()

#: 지금 Postgres 로 돌고 있는가? (DB마다 다르게 처리해야 할 곳에서 쓴다)
IS_POSTGRES = engine.dialect.name == "postgresql"

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    """FastAPI 의존성: 요청 하나당 DB 세션 하나."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
