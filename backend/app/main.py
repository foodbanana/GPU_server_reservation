"""FastAPI 앱 만들기 — 테이블 생성, GPU 등록, 라우터 연결."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_config
from app.database import Base, SessionLocal, engine
from app.models import (  # noqa: F401  (Gpu/Reservation/User 는 테이블 등록에 필요)
    Gpu,
    Reservation,
    User,
    ensure_overlap_constraint,
)
from app.routers import admin, auth, gpus, reservations
from app.seed import seed_gpus
from app.static_files import mount_frontend


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # 앱을 켤 때: 없는 테이블을 만들고, config.yaml 기준으로 GPU 12장을 등록·갱신한다.
    Base.metadata.create_all(bind=engine)
    # Postgres 면 '시간 겹침 금지' 제약도 걸어 둔다 (SQLite 면 아무 일도 안 한다).
    ensure_overlap_constraint(engine)
    with SessionLocal() as db:
        seed_gpus(db)
    yield


app = FastAPI(
    title="연구실 GPU 예약 시스템",
    description="GPU 서버 3대(12장)를 겹치지 않게 예약하는 서비스. 모든 시간은 한국 시간(KST) 기준입니다.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(gpus.router)
app.include_router(reservations.router)
app.include_router(admin.router)


@app.get("/api/health", tags=["기타"])
def health() -> dict[str, str]:
    """서버가 살아 있는지 확인용."""
    return {"status": "ok"}


# 빌드된 Vue 화면 서빙 (Phase 5).
# 반드시 맨 마지막에 붙인다: 먼저 등록된 /api/... 와 /docs 가 우선이고,
# 남은 모든 주소("/", "/my", "/admin" 등)만 화면 쪽으로 넘어간다.
mount_frontend(app, get_config().static_dir)
