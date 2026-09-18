"""예약 생성 / 조회 / 취소 / 조기 종료."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app import timeutil
from app.database import get_db
from app.deps import get_current_user
from app.models import Gpu, Reservation, STATUS_ACTIVE, STATUS_CANCELLED, User
from app.schemas import ReservationCreate, ReservationOut
from app.services.reservation_rules import (
    CONCURRENT_CONFLICT_MESSAGE,
    ConflictError,
    RuleError,
    is_overlap_violation,
    validate_reservation,
)

router = APIRouter(prefix="/api/reservations", tags=["예약"])


def _with_relations(query):
    return query.options(
        joinedload(Reservation.user), joinedload(Reservation.gpu)
    )


@router.post("", response_model=ReservationOut, status_code=status.HTTP_201_CREATED)
def create_reservation(
    body: ReservationCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Reservation:
    """예약을 만든다.

    규칙 위반은 400, 시간이 겹치면 409로 응답한다.

    두 사람이 같은 순간에 눌러도 한 명만 성공해야 한다. 이건 DB가 보장한다.
    - SQLite: '겹침 확인 → 저장'을 하나의 트랜잭션(BEGIN IMMEDIATE) 안에서 처리
    - Postgres: 테이블의 겹침 금지 제약이 나중에 온 INSERT 를 거부
    두 경우 모두 database.py / models.py 참고.
    """
    gpu = db.get(Gpu, body.gpu_id)
    if gpu is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="없는 GPU입니다."
        )

    start_at = timeutil.to_naive_kst(body.start_at)
    end_at = timeutil.to_naive_kst(body.end_at)

    try:
        validate_reservation(db, gpu, start_at, end_at)
    except RuleError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except ConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    reservation = Reservation(
        gpu_id=gpu.id,
        user_id=user.id,
        start_at=start_at,
        end_at=end_at,
        status=STATUS_ACTIVE,
    )
    db.add(reservation)
    try:
        db.commit()
    except IntegrityError as exc:
        # 사전 검사(validate_reservation)를 통과했는데도 저장이 거부됐다면
        # 바로 그 사이에 다른 사람이 같은 시간을 먼저 넣었다는 뜻이다.
        # (Postgres 의 겹침 금지 제약이 막아 준 경우 — models.py 참고)
        db.rollback()
        if not is_overlap_violation(exc):
            raise
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=CONCURRENT_CONFLICT_MESSAGE
        )
    db.refresh(reservation)
    return reservation


@router.get("", response_model=list[ReservationOut])
def list_reservations(
    start: datetime = Query(..., description="조회 시작 (예: 2026-01-05T00:00:00+09:00)"),
    end: datetime = Query(..., description="조회 끝"),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> list[Reservation]:
    """타임라인 화면용. 기간과 겹치는 모든 active 예약."""
    start_at = timeutil.to_naive_kst(start)
    end_at = timeutil.to_naive_kst(end)
    query = _with_relations(
        select(Reservation).where(
            Reservation.status == STATUS_ACTIVE,
            Reservation.start_at < end_at,
            Reservation.end_at > start_at,
        )
    ).order_by(Reservation.start_at)
    return list(db.scalars(query).all())


@router.get("/me", response_model=list[ReservationOut])
def list_my_reservations(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Reservation]:
    """내 예약 목록 (취소한 것 포함, 최근 것부터)."""
    query = _with_relations(
        select(Reservation).where(Reservation.user_id == user.id)
    ).order_by(Reservation.start_at.desc())
    return list(db.scalars(query).all())


def _get_owned_reservation(
    reservation_id: int, db: Session, user: User
) -> Reservation:
    """본인 예약(또는 관리자)만 가져온다. 아니면 404/403."""
    reservation = db.scalar(
        _with_relations(select(Reservation).where(Reservation.id == reservation_id))
    )
    if reservation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="없는 예약입니다."
        )
    if reservation.user_id != user.id and not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="본인의 예약만 취소하거나 종료할 수 있습니다.",
        )
    return reservation


@router.delete("/{reservation_id}", response_model=ReservationOut)
def cancel_reservation(
    reservation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Reservation:
    """예약 취소. 아직 시작하지 않은 예약만 취소할 수 있다(SPEC 7장).

    행을 지우지 않고 status 를 cancelled 로 바꾼다.
    """
    reservation = _get_owned_reservation(reservation_id, db, user)

    if reservation.status == STATUS_CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="이미 취소된 예약입니다."
        )
    if reservation.start_at <= timeutil.now_kst():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 시작된 예약은 취소할 수 없습니다. 조기 종료를 이용해 주세요.",
        )

    reservation.status = STATUS_CANCELLED
    db.commit()
    db.refresh(reservation)
    return reservation


@router.post("/{reservation_id}/end-now", response_model=ReservationOut)
def end_reservation_now(
    reservation_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Reservation:
    """조기 종료. 사용 중인 예약의 종료 시각을 '현재 시각 정시 올림'으로 당긴다(SPEC 7장).

    남은 시간은 곧바로 다른 사람이 예약할 수 있게 된다.
    """
    reservation = _get_owned_reservation(reservation_id, db, user)

    if reservation.status != STATUS_ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="취소된 예약은 종료할 수 없습니다.",
        )

    now = timeutil.now_kst()
    if now < reservation.start_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="아직 시작하지 않은 예약입니다. 취소를 이용해 주세요.",
        )
    if now >= reservation.end_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="이미 끝난 예약입니다."
        )

    new_end = timeutil.ceil_hour(now)
    if new_end <= reservation.start_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="예약이 방금 시작되어 지금은 종료할 수 없습니다. 잠시 후 다시 시도해 주세요.",
        )
    if new_end >= reservation.end_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="반납할 시간이 남아 있지 않습니다. 곧 예약이 끝납니다.",
        )

    reservation.end_at = new_end
    db.commit()
    db.refresh(reservation)
    return reservation
