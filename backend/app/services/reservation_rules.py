"""예약 규칙 검사 — 백엔드의 단일 창구 (PLAN 5장).

예약 생성도, (Phase 4의) 관리자 수정도 모두 이 함수를 거친다.
검사 순서와 '관리자도 적용되는지' 여부는 PLAN 5장 표와 같다.

| # | 검사                                          | 관리자도 적용? |
|---|-----------------------------------------------|----------------|
| 1 | start_at, end_at 이 정시(분·초 0)인가            | 항상           |
| 2 | end_at > start_at 인가                          | 항상           |
| 3 | start_at 이 '현재 시각 정시 내림' 이상인가        | 항상           |
| 4 | start_at 이 지금부터 14일 이내인가               | 관리자는 무시   |
| 5 | 길이가 GPU 분류의 min~max 범위인가                | 관리자는 무시   |
| 6 | 같은 GPU의 다른 active 예약과 겹치는가            | 항상 (예외 없음)|
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import timeutil
from app.config import Config, get_config
from app.models import Gpu, Reservation, STATUS_ACTIVE


class RuleError(Exception):
    """규칙 위반. HTTP 400으로 응답한다."""


class ConflictError(Exception):
    """다른 예약과 시간이 겹침. HTTP 409로 응답한다."""


def validate_reservation(
    db: Session,
    gpu: Gpu,
    start_at: datetime,
    end_at: datetime,
    *,
    as_admin: bool = False,
    exclude_reservation_id: int | None = None,
    config: Config | None = None,
) -> list[str]:
    """예약 시간이 규칙에 맞는지 검사한다.

    문제가 있으면 첫 번째로 걸린 규칙의 한국어 메시지와 함께
    RuleError(규칙 위반) 또는 ConflictError(시간 겹침)를 던진다.
    문제가 없으면 경고 메시지 목록(보통 빈 목록)을 돌려준다.
    관리자가 규칙을 건너뛰고 저장한 경우에만 경고가 담긴다.
    """
    config = config or get_config()
    rules = config.rules
    warnings: list[str] = []

    # 1. 정시(분·초 0)인가 — 항상 적용
    if not timeutil.is_on_the_hour(start_at) or not timeutil.is_on_the_hour(end_at):
        raise RuleError("예약 시각은 정시여야 합니다. (분·초는 0, 예: 14:00)")

    # 2. 종료가 시작보다 뒤인가 — 항상 적용
    if end_at <= start_at:
        raise RuleError("종료 시각은 시작 시각보다 뒤여야 합니다.")

    now = timeutil.now_kst()

    # 3. 시작 시각이 '현재 시각이 속한 정시(내림)' 이상인가 — 항상 적용
    #    예: 지금이 14:20이면 14:00 시작은 허용(지금 당장 쓰기 시작), 13:00은 거부.
    earliest_start = timeutil.floor_hour(now)
    if start_at < earliest_start:
        raise RuleError(
            f"지난 시간은 예약할 수 없습니다. "
            f"{timeutil.format_kst(earliest_start)} 이후부터 예약할 수 있습니다."
        )

    # 4. 시작 시각이 지금부터 N일 이내인가 — 관리자는 무시 가능
    latest_start = earliest_start + timedelta(days=rules.booking_horizon_days)
    if start_at > latest_start:
        if not as_admin:
            raise RuleError(
                f"예약은 지금부터 {rules.booking_horizon_days}일 이내까지만 할 수 있습니다. "
                f"({timeutil.format_kst(latest_start)} 까지)"
            )
        warnings.append(
            f"{rules.booking_horizon_days}일 예약 가능 범위를 무시하고 저장했습니다."
        )

    # 5. 예약 길이가 GPU 분류의 최소~최대 범위인가 — 관리자는 무시 가능
    hours = int((end_at - start_at).total_seconds() // 3600)
    rule = rules.for_category(gpu.category)
    if hours < rule.min_hours or hours > rule.max_hours:
        if not as_admin:
            raise RuleError(
                f"{gpu.category_label} GPU는 최소 {rule.min_hours}시간, "
                f"최대 {rule.max_hours}시간까지 예약할 수 있습니다. "
                f"(신청한 길이: {hours}시간)"
            )
        warnings.append(
            f"{gpu.category_label} 예약 시간 제한"
            f"({rule.min_hours}~{rule.max_hours}시간)을 무시하고 저장했습니다."
        )

    # 6. 같은 GPU의 다른 active 예약과 겹치는가 — 관리자도 예외 없음
    conflict = find_conflict(
        db, gpu.id, start_at, end_at, exclude_reservation_id=exclude_reservation_id
    )
    if conflict is not None:
        raise ConflictError(
            f"이미 예약된 시간입니다. {gpu.label} 의 "
            f"{timeutil.format_kst(conflict.start_at)} ~ "
            f"{timeutil.format_kst(conflict.end_at)} 예약과 겹칩니다."
        )

    return warnings


def find_conflict(
    db: Session,
    gpu_id: int,
    start_at: datetime,
    end_at: datetime,
    *,
    exclude_reservation_id: int | None = None,
) -> Reservation | None:
    """시간이 겹치는 active 예약 하나를 찾는다. 없으면 None.

    겹침 조건 (SPEC 5장): 새 시작 < 기존 종료 AND 새 종료 > 기존 시작
    끝나는 시각과 시작 시각이 같은 경우(10시 종료 ↔ 10시 시작)는 겹치지 않는다.
    """
    query = (
        select(Reservation)
        .where(
            Reservation.gpu_id == gpu_id,
            Reservation.status == STATUS_ACTIVE,
            Reservation.start_at < end_at,
            Reservation.end_at > start_at,
        )
        .order_by(Reservation.start_at)
    )
    if exclude_reservation_id is not None:
        # 수정할 때는 자기 자신과 겹친다고 하면 안 된다.
        query = query.where(Reservation.id != exclude_reservation_id)
    return db.scalars(query).first()
