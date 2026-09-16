"""두 사람이 같은 순간에 같은 시간을 신청해도 한 명만 성공해야 한다 (SPEC 5장).

database.py 의 BEGIN IMMEDIATE 트랜잭션이 실제로 동작하는지 확인한다.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

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
