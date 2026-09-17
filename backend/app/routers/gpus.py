"""GPU 목록과 프론트엔드용 설정값."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app import timeutil
from app.config import get_config
from app.database import get_db
from app.deps import get_current_user
from app.models import Gpu, Reservation, STATUS_ACTIVE, User
from app.schemas import ConfigOut, GpuOut, ReservationOut

router = APIRouter(prefix="/api", tags=["GPU"])


@router.get("/config", response_model=ConfigOut)
def read_config() -> ConfigOut:
    """프론트엔드가 쓰는 설정값. 진짜 판정은 언제나 서버가 한다."""
    config = get_config()
    return ConfigOut(
        timezone=config.timezone,
        slot_minutes=config.rules.slot_minutes,
        timeline_days=config.rules.timeline_days,
    )


@router.get("/gpus", response_model=list[GpuOut])
def list_gpus(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[Gpu]:
    return list(db.scalars(select(Gpu).order_by(Gpu.sort_order)).all())


@router.get("/gpus/{gpu_id}/reservations", response_model=list[ReservationOut])
def list_gpu_reservations(
    gpu_id: int,
    start: datetime = Query(..., description="조회 시작 (예: 2026-01-05T00:00:00+09:00)"),
    end: datetime | None = Query(
        None, description="조회 끝. 비워 두면 앞으로의 예약을 끝까지 모두 준다."
    ),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[Reservation]:
    """예약 신청 화면에서 '이미 예약된 시간대'를 보여주기 위한 목록.

    예약 가능 기간 제한이 없어졌으므로, end 를 생략하면 기간 제한 없이
    start 이후로 이어지는 예약을 모두 돌려준다.
    """
    if db.get(Gpu, gpu_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="없는 GPU입니다."
        )

    start_at = timeutil.to_naive_kst(start)
    query = (
        select(Reservation)
        .options(joinedload(Reservation.user), joinedload(Reservation.gpu))
        .where(
            Reservation.gpu_id == gpu_id,
            Reservation.status == STATUS_ACTIVE,
            Reservation.end_at > start_at,
        )
        .order_by(Reservation.start_at)
    )
    if end is not None:
        query = query.where(Reservation.start_at < timeutil.to_naive_kst(end))
    return list(db.scalars(query).all())
