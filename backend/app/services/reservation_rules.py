"""예약 규칙 검사 — 백엔드의 단일 창구 (PLAN 5장).

예약 생성도, 관리자의 시간 수정도 모두 이 함수를 거친다.

| # | 검사                                          | 관리자도 적용? |
|---|-----------------------------------------------|----------------|
| 1 | start_at, end_at 이 정시(분·초 0)인가            | 항상           |
| 2 | end_at > start_at 인가                          | 항상           |
| 3 | start_at 이 '현재 시각 정시 내림' 이상인가        | 항상 (예외 1개) |
| 4 | 같은 GPU의 다른 active 예약과 겹치는가            | 항상           |

검사 3의 예외: **이미 시작된 예약의 시작 시각을 그대로 두고 종료 시각만 바꾸는 수정**.
사용 중인 예약을 관리자가 연장해 주려면 시작 시각이 과거일 수밖에 없기 때문이다.
이때는 대신 '새 종료 시각이 지난 시각이면 안 된다'를 검사한다.

예약 길이 제한(단주기 최대·장주기 최소, 최대 길이)과 '14일 이내 시작' 제한은
연구실에서 협의해 쓰기로 하여 없앴다. 그래서 '관리자만 무시할 수 있는 규칙'도
더 이상 없고, 관리자와 일반 사용자에게 같은 규칙이 적용된다.
(단주기/장주기 구분 자체는 화면 표시·분류용으로 그대로 남아 있다)
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import timeutil
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
    exclude_reservation_id: int | None = None,
    current_start_at: datetime | None = None,
) -> None:
    """예약 시간이 규칙에 맞는지 검사한다.

    문제가 있으면 첫 번째로 걸린 규칙의 한국어 메시지와 함께
    RuleError(규칙 위반) 또는 ConflictError(시간 겹침)를 던진다.
    문제가 없으면 아무 일도 하지 않는다.

    current_start_at: 기존 예약을 수정할 때 그 예약의 지금 시작 시각.
        새 start_at 이 이 값과 같으면 '시작 시각을 건드리지 않는 수정'이므로
        지난 시각 검사(3번)를 건너뛴다. 사용 중인 예약의 종료만 늘리거나
        줄이는 수정을 허용하기 위한 것이다.
    """
    # 1. 정시(분·초 0)인가
    if not timeutil.is_on_the_hour(start_at) or not timeutil.is_on_the_hour(end_at):
        raise RuleError("예약 시각은 정시여야 합니다. (분·초는 0, 예: 14:00)")

    # 2. 종료가 시작보다 뒤인가
    if end_at <= start_at:
        raise RuleError("종료 시각은 시작 시각보다 뒤여야 합니다.")

    # 3. 시작 시각이 '현재 시각이 속한 정시(내림)' 이상인가
    #    예: 지금이 14:20이면 14:00 시작은 허용(지금 당장 쓰기 시작), 13:00은 거부.
    earliest_start = timeutil.floor_hour(timeutil.now_kst())
    시작을그대로둠 = current_start_at is not None and start_at == current_start_at

    if 시작을그대로둠:
        # 이미 시작된 예약의 종료 시각만 바꾸는 경우.
        # 시작이 과거인 것은 당연하므로 넘어가고, 대신 종료가 과거가 되지 않게 막는다.
        if end_at < earliest_start:
            raise RuleError(
                f"종료 시각을 지난 시간으로 바꿀 수는 없습니다. "
                f"{timeutil.format_kst(earliest_start)} 이후로 정해 주세요."
            )
    elif start_at < earliest_start:
        raise RuleError(
            f"지난 시간은 예약할 수 없습니다. "
            f"{timeutil.format_kst(earliest_start)} 이후부터 예약할 수 있습니다."
        )

    # 4. 같은 GPU의 다른 active 예약과 겹치는가
    conflict = find_conflict(
        db, gpu.id, start_at, end_at, exclude_reservation_id=exclude_reservation_id
    )
    if conflict is not None:
        raise ConflictError(
            f"이미 예약된 시간입니다. {gpu.label} 의 "
            f"{timeutil.format_kst(conflict.start_at)} ~ "
            f"{timeutil.format_kst(conflict.end_at)} 예약과 겹칩니다."
        )


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
