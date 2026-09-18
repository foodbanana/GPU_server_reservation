"""관리자 전용 API (Phase 4).

- 전체 예약 목록 보기
- 예약의 시작·종료 시각 수정 (GPU·예약자는 바꿀 수 없다)
- 예약 강제 취소
- 가입자 목록 보기
- 가입자에게 관리자 권한 주기 / 뺏기 (계정을 고치거나 지우는 기능은 여전히 없다)

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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app import timeutil
from app.database import get_db
from app.deps import get_current_admin
from app.models import Reservation, STATUS_ACTIVE, STATUS_CANCELLED, User
from app.schemas import (
    AdminReservationOut,
    AdminRoleResult,
    AdminRoleUpdate,
    AdminUserOut,
    ReservationTimeUpdate,
)
from app.services import accounts
from app.services.reservation_rules import (
    CONCURRENT_CONFLICT_MESSAGE,
    ConflictError,
    RuleError,
    is_overlap_violation,
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
    try:
        db.commit()
    except IntegrityError as exc:
        # 사전 검사와 저장 사이에 다른 사람이 그 시간을 먼저 차지한 경우.
        # (Postgres 의 겹침 금지 제약이 막아 준다 — models.py 참고)
        db.rollback()
        if not is_overlap_violation(exc):
            raise
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=CONCURRENT_CONFLICT_MESSAGE
        )
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
    계정을 고치거나 지우는 기능은 일부러 만들지 않았다.
    바꿀 수 있는 것은 관리자 권한 하나뿐이다 (아래 update_user_role).
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
            is_super_admin=accounts.is_super_admin_email(user.email),
            created_at=user.created_at,
            active_reservation_count=counts.get(user.id, 0),
        )
        for user in users
    ]


# ---------- 관리자 권한 주기 / 뺏기 ----------

@router.patch("/users/role", response_model=AdminRoleResult)
def update_user_role(
    body: AdminRoleUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(get_current_admin),
) -> AdminRoleResult:
    """가입한 사람에게 관리자 권한을 주거나 뺏는다.

    터미널의 `scripts/set_admin.py` 와 **완전히 같은 규칙**을 웹으로 연 것이다
    (판단은 app/services/accounts.py 가 한다).

    막는 경우 (모두 400):
    - 최고 관리자(환경변수 GPU_RESERVE_SUPER_ADMIN_EMAIL)의 권한 해제 — 본인도 못 한다
    - 자기 자신의 권한 해제 — 관리자 화면에서 바로 튕겨 나가 혼란스러우므로
    - 마지막 남은 관리자의 권한 해제 — 아무도 관리자 화면에 못 들어가게 되므로

    없는 사용자면 404. 관리자가 아닌 사람은 라우터 단에서 403으로 막힌다.
    이미 관리자인 사람을 또 승격하는 것처럼 바뀌는 게 없는 요청은 오류가 아니라
    200 으로 "바뀐 것이 없습니다" 를 돌려준다.
    """
    # 1) 대상 찾기 (user_id 또는 email — 스키마가 둘 중 하나만 오도록 검사한다)
    if body.user_id is not None:
        target = db.get(User, body.user_id)
        못찾음 = f"id {body.user_id} 인 사용자를 찾지 못했습니다."
    else:
        target = accounts.find_user(db, str(body.email))
        못찾음 = f"가입된 적 없는 이메일입니다: {body.email}"

    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=못찾음)

    # 2) 규칙 검사 + 반영
    try:
        결과, user = accounts.change_admin_status(
            db, target=target, make_admin=body.is_admin, actor=actor
        )
    except accounts.AccountError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    안내 = {
        accounts.PROMOTED: (
            f"{user.name} 님이 이제 관리자입니다. "
            "본인이 로그인 중이었다면 로그아웃했다가 다시 로그인해야 관리자 메뉴가 보입니다."
        ),
        accounts.REVOKED: (
            f"{user.name} 님의 관리자 권한을 해제했습니다. "
            "그 사람 화면에서 관리자 메뉴가 사라집니다."
        ),
        accounts.ALREADY_ADMIN: f"{user.name} 님은 이미 관리자입니다. 바뀐 것이 없습니다.",
        accounts.ALREADY_NORMAL: f"{user.name} 님은 원래 관리자가 아닙니다. 바뀐 것이 없습니다.",
    }[결과]

    return AdminRoleResult(
        result=결과,
        user_id=user.id,
        name=user.name,
        email=user.email,
        is_admin=user.is_admin,
        message=안내,
    )
