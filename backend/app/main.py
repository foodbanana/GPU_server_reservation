"""FastAPI 앱 만들기 — 테이블 생성, GPU 등록, 라우터 연결."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_config
from app.db_init import initialize_database, should_init_on_startup
from app.models import Gpu, Reservation, User  # noqa: F401  (테이블 등록에 필요)
from app.routers import admin, auth, gpus, reservations
from app.static_files import mount_frontend


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # 앱을 켤 때 테이블·겹침 제약·GPU 12장을 준비한다.
    # Vercel(서버리스)에서는 콜드스타트마다 반복되면 느리므로 건너뛴다.
    # 그때는 사용자가 scripts/init_db.py 로 한 번만 실행한다 (app/db_init.py 참고).
    if should_init_on_startup():
        initialize_database()
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
