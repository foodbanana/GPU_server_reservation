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
from app.schemas import CategoryRuleOut, ConfigOut, GpuOut, ReservationOut

router = APIRouter(prefix="/api", tags=["GPU"])


@router.get("/config", response_model=ConfigOut)
def read_config() -> ConfigOut:
    """프론트엔드가 편의용 검사에 쓸 규칙값. 진짜 판정은 언제나 서버가 한다."""
    config = get_config()
    rules = config.rules
    return ConfigOut(
        timezone=config.timezone,
        slot_minutes=rules.slot_minutes,
        booking_horizon_days=rules.booking_horizon_days,
        short=CategoryRuleOut(
            min_hours=rules.short.min_hours, max_hours=rules.short.max_hours
        ),
        long=CategoryRuleOut(
            min_hours=rules.long.min_hours, max_hours=rules.long.max_hours
        ),
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
    end: datetime = Query(..., description="조회 끝"),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[Reservation]:
    """예약 신청 화면에서 '이미 예약된 시간대'를 보여주기 위한 목록."""
    if db.get(Gpu, gpu_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="없는 GPU입니다."
        )

    start_at = timeutil.to_naive_kst(start)
    end_at = timeutil.to_naive_kst(end)
    query = (
        select(Reservation)
        .options(joinedload(Reservation.user), joinedload(Reservation.gpu))
        .where(
            Reservation.gpu_id == gpu_id,
            Reservation.status == STATUS_ACTIVE,
            Reservation.start_at < end_at,
            Reservation.end_at > start_at,
        )
        .order_by(Reservation.start_at)
    )
    return list(db.scalars(query).all())
