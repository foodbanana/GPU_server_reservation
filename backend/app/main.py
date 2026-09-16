"""FastAPI 앱 만들기 — 테이블 생성, GPU 등록, 라우터 연결."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import Base, SessionLocal, engine
from app.models import Gpu, Reservation, User  # noqa: F401  (테이블 등록에 필요)
from app.routers import auth, gpus, reservations
from app.seed import seed_gpus


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # 앱을 켤 때: 없는 테이블을 만들고, config.yaml 기준으로 GPU 12장을 등록·갱신한다.
    Base.metadata.create_all(bind=engine)
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


@app.get("/api/health", tags=["기타"])
def health() -> dict[str, str]:
    """서버가 살아 있는지 확인용."""
    return {"status": "ok"}
