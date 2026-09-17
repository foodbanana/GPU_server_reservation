"""관리자 전용 API (Phase 4).

- 전체 예약 목록 보기
- 예약의 시작·종료 시각 수정 (GPU·예약자는 바꿀 수 없다)
- 예약 강제 취소
- 가입자 목록 보기 (보기 전용. 계정을 고치거나 지우는 기능은 없다)

이 라우터의 모든 경로는 get_current_admin 을 거치므로,
관리자가 아닌 사용자는 주소를 직접 입력해도 403 으로 막힌다.

수정할 때의 규칙(PLAN 5장):
- 예약 길이 제한과 '14일 이내 시작' 제한이 없어졌으므로 '관리자만 무시할 수 있는
  규칙'도 없다. 관리자 수정에도 일반 예약과 똑같은 규칙이 적용된다.
- 겹침은 관리자에게도 예외 없이 거부된다 → 409
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app import timeutil
from app.database import get_db
from app.deps import get_current_admin
from app.models import Reservation, STATUS_ACTIVE, STATUS_CANCELLED, User
from app.schemas import AdminReservationOut, AdminUserOut, ReservationTimeUpdate
from app.services.reservation_rules import (
    ConflictError,
    RuleError,
    validate_reservation,
)

router = APIRouter(
    prefix="/api/admin",
    tags=["관리자"],
    dependencies=[Depends(get_current_admin)],
)


def _load(reservation_id: int, db: Session) -> Reservation:
    reservation = db.scalar(
        select(Reservation)
        .options(joinedload(Reservation.user), joinedload(Reservation.gpu))
        .where(Reservation.id == reservation_id)
    )
    if reservation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="없는 예약입니다."
        )
    return reservation


@router.get("/reservations", response_model=list[AdminReservationOut])
def list_all_reservations(
    status_filter: str = Query(
        "all",
        alias="status",
        pattern="^(all|active|cancelled)$",
        description="all=전체, active=유효한 예약, cancelled=취소된 예약",
    ),
    period: str = Query(
        "all",
        pattern="^(all|current)$",
        description="all=지난 예약 포함, current=아직 끝나지 않은 예약만",
    ),
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[Reservation]:
    """전체 예약 목록. 최근(시작이 늦은) 것부터 보여준다."""
    query = select(Reservation).options(
        joinedload(Reservation.user), joinedload(Reservation.gpu)
    )
    if status_filter != "all":
        query = query.where(Reservation.status == status_filter)
    if period == "current":
        query = query.where(Reservation.end_at > timeutil.now_kst())

    query = query.order_by(Reservation.start_at.desc()).limit(limit).offset(offset)
    return list(db.scalars(query).all())


@router.patch("/reservations/{reservation_id}", response_model=AdminReservationOut)
def update_reservation_time(
    reservation_id: int,
    body: ReservationTimeUpdate,
    db: Session = Depends(get_db),
) -> Reservation:
    """예약의 시작·종료 시각만 바꾼다.

    다른 예약과 겹치면 409, 정시·순서·지난 시간 검사에 걸리면 400 으로 거부한다.
    예약 길이 제한은 없으므로 얼마든지 길게 늘릴 수 있다.

    **이미 시작된(사용 중인) 예약도 종료 시각만 바꾸면 연장·단축할 수 있다.**
    시작 시각을 그대로 두면 '지난 시각' 검사를 건너뛰기 때문이다
    (services/reservation_rules.py 의 current_start_at 참고).
    시작 시각까지 과거로 옮기려고 하면 그때는 400 으로 거부된다.
    """
    reservation = _load(reservation_id, db)

    if reservation.status != STATUS_ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="취소된 예약은 수정할 수 없습니다.",
        )

    start_at = timeutil.to_naive_kst(body.start_at)
    end_at = timeutil.to_naive_kst(body.end_at)

    try:
        validate_reservation(
            db,
            reservation.gpu,
            start_at,
            end_at,
            # 자기 자신과는 겹친다고 하면 안 된다
            exclude_reservation_id=reservation.id,
            # 시작 시각을 건드리지 않으면 사용 중인 예약도 종료만 바꿀 수 있다
            current_start_at=reservation.start_at,
        )
    except RuleError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except ConflictError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    reservation.start_at = start_at
    reservation.end_at = end_at
    db.commit()
    db.refresh(reservation)
    return reservation


@router.delete("/reservations/{reservation_id}", response_model=AdminReservationOut)
def force_cancel_reservation(
    reservation_id: int,
    db: Session = Depends(get_db),
) -> Reservation:
    """예약 강제 취소. 이미 시작했거나 끝난 예약도 지울 수 있다.

    기록을 남기기 위해 행을 삭제하지 않고 status 를 cancelled 로 바꾼다(PLAN 3장).
    """
    reservation = _load(reservation_id, db)

    if reservation.status == STATUS_CANCELLED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="이미 취소된 예약입니다."
        )

    reservation.status = STATUS_CANCELLED
    db.commit()
    db.refresh(reservation)
    return reservation


# ---------- 가입자 목록 (보기 전용) ----------

@router.get("/users", response_model=list[AdminUserOut])
def list_users(db: Session = Depends(get_db)) -> list[AdminUserOut]:
    """가입한 사람 목록. 가입이 빠른 사람부터 보여준다.

    비밀번호 해시는 절대 내보내지 않는다 (AdminUserOut 에 필드 자체가 없다).
    계정을 고치거나 지우는 기능은 일부러 만들지 않았다 — 보기 전용이다.
    """
    now = timeutil.now_kst()

    # 사람마다 '지금 사용 중이거나 앞으로 예정된 예약'이 몇 건인지 한 번에 센다.
    # (취소된 예약과 이미 끝난 예약은 세지 않는다)
    counts = dict(
        db.execute(
            select(Reservation.user_id, func.count(Reservation.id))
            .where(
                Reservation.status == STATUS_ACTIVE,
                Reservation.end_at > now,
            )
            .group_by(Reservation.user_id)
        ).all()
    )

    users = db.scalars(select(User).order_by(User.created_at, User.id)).all()
    return [
        AdminUserOut(
            id=user.id,
            name=user.name,
            email=user.email,
            is_admin=user.is_admin,
            created_at=user.created_at,
            active_reservation_count=counts.get(user.id, 0),
        )
        for user in users
    ]
