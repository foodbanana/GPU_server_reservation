"""두 사람이 같은 순간에 같은 시간을 신청해도 한 명만 성공해야 한다 (SPEC 5장).

DB에 따라 이걸 지켜 주는 장치가 다르다. 두 경우 모두 여기서 확인한다.
- SQLite   : database.py 의 BEGIN IMMEDIATE 트랜잭션 잠금
- Postgres : models.py 의 겹침 금지 제약(EXCLUDE)

첫 번째 테스트는 API 를 실제로 동시에 두드려 보는 것이라 두 DB 모두에서 돈다.
두 번째 테스트는 Postgres 전용으로, 규칙 검사를 아예 건너뛰고 DB에 직접 넣어 보며
"마지막 안전장치가 정말 켜져 있는지"를 확인한다.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.database import IS_POSTGRES
from app.models import STATUS_ACTIVE, STATUS_CANCELLED, Gpu, Reservation, User
from app.services.reservation_rules import is_overlap_violation
from tests.conftest import auth_headers, create_reservation, gpu_id_by


def test_동시에_같은_시간을_신청하면_한_명만_성공한다(client):
    사용자A = auth_headers(client, email="a@example.com", name="A")
    사용자B = auth_headers(client, email="b@example.com", name="B")
    gpu_id = gpu_id_by(client, 사용자A, "short")

    start = datetime(2026, 1, 6, 10, 0)
    end = datetime(2026, 1, 6, 14, 0)

    # 두 요청이 최대한 같은 순간에 출발하도록 맞춘다
    출발선 = threading.Barrier(2)

    def 신청(headers: dict):
        출발선.wait(timeout=10)
        return create_reservation(client, headers, gpu_id, start, end).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        결과 = sorted(pool.map(신청, [사용자A, 사용자B]))

    assert 결과 == [201, 409], f"기대: 한 명 성공 한 명 거부, 실제: {결과}"

    # DB에도 예약이 딱 하나만 남아 있어야 한다
    목록 = client.get(
        "/api/reservations",
        headers=사용자A,
        params={
            "start": "2026-01-06T00:00:00+09:00",
            "end": "2026-01-07T00:00:00+09:00",
        },
    ).json()
    assert len(목록) == 1


@pytest.mark.skipif(
    not IS_POSTGRES, reason="Postgres 전용 (SQLite 에는 EXCLUDE 제약 문법이 없다)"
)
def test_postgres_는_겹치는_예약을_DB에서_직접_거부한다(db_session):
    """규칙 검사를 건너뛰고 DB에 바로 넣어도 겹치면 거부돼야 한다.

    파이썬 쪽 사전 검사(find_conflict)가 뚫리더라도 DB가 마지막에 막아 준다는 뜻이다.
    함께 확인하는 것:
    - 취소된 예약은 검사 대상이 아니다 (취소한 시간은 다시 예약할 수 있어야 하니까)
    - 끝나는 시각과 시작 시각이 맞닿은 경우는 겹치는 게 아니다 (SPEC 5장)
    """
    gpu = db_session.scalars(select(Gpu)).first()
    user = User(name="A", email="pg-a@example.com", password_hash="x")
    db_session.add(user)
    db_session.commit()

    def 예약(start_hour: int, end_hour: int, status: str = STATUS_ACTIVE) -> Reservation:
        return Reservation(
            gpu_id=gpu.id,
            user_id=user.id,
            start_at=datetime(2026, 1, 6, start_hour, 0),
            end_at=datetime(2026, 1, 6, end_hour, 0),
            status=status,
        )

    db_session.add(예약(10, 14))
    db_session.commit()

    # 10~14시와 겹치는 12~16시 -> DB가 거부해야 한다
    db_session.add(예약(12, 16))
    with pytest.raises(IntegrityError) as 오류:
        db_session.commit()
    assert is_overlap_violation(오류.value), "겹침 제약이 아닌 다른 이유로 거부됐다"
    db_session.rollback()

    # 같은 시간이라도 '취소됨'이면 들어가야 한다
    db_session.add(예약(12, 16, STATUS_CANCELLED))
    db_session.commit()

    # 14시 종료 ↔ 14시 시작은 겹치는 게 아니다
    db_session.add(예약(14, 16))
    db_session.commit()

    남은예약 = db_session.scalars(
        select(Reservation).where(Reservation.status == STATUS_ACTIVE)
    ).all()
    assert len(남은예약) == 2
