"""시간 겹침(중복 예약) 검사 테스트 (SPEC 5장, PLAN 5장 표의 6번).

겹침 조건: 새 시작 < 기존 종료 AND 새 종료 > 기존 시작
경계가 맞닿는 경우(10시 종료 ↔ 10시 시작)는 겹치지 않는다.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from tests.conftest import auth_headers, create_reservation, gpu_id_by, iso


@pytest.fixture
def headers(client):
    return auth_headers(client, email="owner@example.com", name="홍길동")


@pytest.fixture
def other_headers(client):
    return auth_headers(client, email="other@example.com", name="김철수")


@pytest.fixture
def short_gpu(client, headers):
    return gpu_id_by(client, headers, "short")


@pytest.fixture
def existing(client, headers, short_gpu, clock):
    """기준이 되는 예약: 2026-01-06 10:00 ~ 14:00"""
    start = datetime(2026, 1, 6, 10, 0)
    end = datetime(2026, 1, 6, 14, 0)
    response = create_reservation(client, headers, short_gpu, start, end)
    assert response.status_code == 201, response.text
    return response.json()


# ---------- 겹치면 거부 ----------

@pytest.mark.parametrize(
    "start_hour, end_hour, 설명",
    [
        (10, 14, "완전히 같은 시간"),
        (11, 13, "기존 예약 안에 들어감"),
        (9, 15, "기존 예약을 감쌈"),
        (8, 11, "앞쪽이 걸침"),
        (13, 16, "뒤쪽이 걸침"),
        (13, 14, "끝부분 한 시간만 걸침"),
        (10, 11, "시작부분 한 시간만 걸침"),
    ],
)
def test_겹치는_예약은_409로_거부된다(
    client, other_headers, short_gpu, existing, start_hour, end_hour, 설명
):
    response = create_reservation(
        client,
        other_headers,
        short_gpu,
        datetime(2026, 1, 6, start_hour, 0),
        datetime(2026, 1, 6, end_hour, 0),
    )
    assert response.status_code == 409, f"{설명}: {response.text}"
    assert "이미 예약된 시간입니다" in response.json()["detail"]


# ---------- 경계가 맞닿는 것은 허용 ----------

def test_기존_종료_시각에_시작하는_예약은_허용된다(client, other_headers, short_gpu, existing):
    """기존 예약이 14:00에 끝나면 14:00 시작은 겹치지 않는다."""
    response = create_reservation(
        client,
        other_headers,
        short_gpu,
        datetime(2026, 1, 6, 14, 0),
        datetime(2026, 1, 6, 18, 0),
    )
    assert response.status_code == 201, response.text


def test_기존_시작_시각에_끝나는_예약은_허용된다(client, other_headers, short_gpu, existing):
    """기존 예약이 10:00에 시작하면 10:00에 끝나는 예약은 겹치지 않는다."""
    response = create_reservation(
        client,
        other_headers,
        short_gpu,
        datetime(2026, 1, 6, 6, 0),
        datetime(2026, 1, 6, 10, 0),
    )
    assert response.status_code == 201, response.text


def test_앞뒤로_빈틈없이_붙여도_모두_허용된다(client, other_headers, short_gpu, existing):
    앞 = create_reservation(
        client, other_headers, short_gpu,
        datetime(2026, 1, 6, 6, 0), datetime(2026, 1, 6, 10, 0),
    )
    뒤 = create_reservation(
        client, other_headers, short_gpu,
        datetime(2026, 1, 6, 14, 0), datetime(2026, 1, 6, 18, 0),
    )
    assert 앞.status_code == 201 and 뒤.status_code == 201
    # 그 사이에 1시간이라도 끼워 넣으려 하면 거부
    가운데 = create_reservation(
        client, other_headers, short_gpu,
        datetime(2026, 1, 6, 11, 0), datetime(2026, 1, 6, 12, 0),
    )
    assert 가운데.status_code == 409


# ---------- 다른 GPU는 서로 영향을 주지 않는다 ----------

def test_다른_GPU에는_같은_시간을_예약할_수_있다(client, headers, other_headers, existing):
    gpus = client.get("/api/gpus", headers=headers).json()
    다른_단주기 = [g for g in gpus if g["category"] == "short" and g["id"] != existing["gpu_id"]][0]
    response = create_reservation(
        client, other_headers, 다른_단주기["id"],
        datetime(2026, 1, 6, 10, 0), datetime(2026, 1, 6, 14, 0),
    )
    assert response.status_code == 201, response.text


# ---------- 취소·조기 종료로 자리가 나면 다시 예약할 수 있다 ----------

def test_취소한_예약_자리는_다시_예약할_수_있다(client, headers, other_headers, short_gpu, existing):
    cancel = client.delete(f"/api/reservations/{existing['id']}", headers=headers)
    assert cancel.status_code == 200, cancel.text
    assert cancel.json()["status"] == "cancelled"

    response = create_reservation(
        client, other_headers, short_gpu,
        datetime(2026, 1, 6, 10, 0), datetime(2026, 1, 6, 14, 0),
    )
    assert response.status_code == 201, response.text


def test_조기_종료하면_남은_시간을_다른_사람이_예약할_수_있다(
    client, headers, other_headers, short_gpu, clock
):
    # 지금(14:20) 사용 중인 예약: 14:00 ~ 20:00
    created = create_reservation(
        client, headers, short_gpu,
        datetime(2026, 1, 5, 14, 0), datetime(2026, 1, 5, 20, 0),
    )
    assert created.status_code == 201, created.text
    reservation_id = created.json()["id"]

    # 남은 시간(16:00~20:00)은 아직 다른 사람이 못 쓴다
    막힘 = create_reservation(
        client, other_headers, short_gpu,
        datetime(2026, 1, 5, 16, 0), datetime(2026, 1, 5, 20, 0),
    )
    assert 막힘.status_code == 409

    # 조기 종료 → 종료 시각이 '현재 시각 정시 올림'인 15:00 으로 당겨진다
    ended = client.post(f"/api/reservations/{reservation_id}/end-now", headers=headers)
    assert ended.status_code == 200, ended.text
    assert ended.json()["end_at"] == iso(datetime(2026, 1, 5, 15, 0))

    # 이제 15:00부터는 다른 사람이 예약할 수 있다
    response = create_reservation(
        client, other_headers, short_gpu,
        datetime(2026, 1, 5, 15, 0), datetime(2026, 1, 5, 20, 0),
    )
    assert response.status_code == 201, response.text


# ---------- 예약 조회 ----------

def test_기간_조회는_겹치는_예약만_돌려준다(client, headers, short_gpu, existing):
    def 조회(start: datetime, end: datetime):
        return client.get(
            "/api/reservations",
            headers=headers,
            params={"start": iso(start), "end": iso(end)},
        ).json()

    assert len(조회(datetime(2026, 1, 6, 0, 0), datetime(2026, 1, 7, 0, 0))) == 1
    # 예약 종료 시각(14:00)부터 시작하는 구간에는 걸리지 않는다
    assert 조회(datetime(2026, 1, 6, 14, 0), datetime(2026, 1, 7, 0, 0)) == []
    assert 조회(datetime(2026, 1, 6, 0, 0), datetime(2026, 1, 6, 10, 0)) == []


def test_예약에_예약자_이름이_담긴다(client, headers, existing):
    목록 = client.get(
        "/api/reservations",
        headers=headers,
        params={
            "start": iso(datetime(2026, 1, 6, 0, 0)),
            "end": iso(datetime(2026, 1, 7, 0, 0)),
        },
    ).json()
    assert 목록[0]["user_name"] == "홍길동"
    assert "서버" in 목록[0]["gpu_label"]


def test_내_예약만_돌려준다(client, headers, other_headers, short_gpu, existing):
    create_reservation(
        client, other_headers, short_gpu,
        datetime(2026, 1, 7, 10, 0), datetime(2026, 1, 7, 14, 0),
    )
    내예약 = client.get("/api/reservations/me", headers=headers).json()
    assert len(내예약) == 1
    assert 내예약[0]["id"] == existing["id"]


def test_특정_GPU의_예약된_시간대_조회(client, headers, short_gpu, existing):
    response = client.get(
        f"/api/gpus/{short_gpu}/reservations",
        headers=headers,
        params={
            "start": iso(datetime(2026, 1, 5, 0, 0)),
            "end": iso(datetime(2026, 1, 20, 0, 0)),
        },
    )
    assert response.status_code == 200
    목록 = response.json()
    assert len(목록) == 1
    assert 목록[0]["start_at"] == iso(datetime(2026, 1, 6, 10, 0))
    assert 목록[0]["end_at"] == iso(datetime(2026, 1, 6, 14, 0))


def test_GPU_예약_조회는_end_를_생략하면_앞으로_전부_돌려준다(
    client, headers, short_gpu, clock, existing
):
    """예약 가능 기간 제한이 없어졌으므로, 예약 신청 화면은 기간 제한 없이 조회한다."""
    먼미래 = create_reservation(client, headers, short_gpu, clock.hour(24 * 90), clock.hour(24 * 90 + 5))
    assert 먼미래.status_code == 201, 먼미래.text

    response = client.get(
        f"/api/gpus/{short_gpu}/reservations",
        headers=headers,
        params={"start": iso(datetime(2026, 1, 5, 0, 0))},
    )
    assert response.status_code == 200
    assert [r["id"] for r in response.json()] == [existing["id"], 먼미래.json()["id"]]


# ---------- 취소 / 조기 종료 규칙 ----------

def test_이미_시작된_예약은_취소할_수_없다(client, headers, short_gpu, clock):
    created = create_reservation(
        client, headers, short_gpu,
        datetime(2026, 1, 5, 14, 0), datetime(2026, 1, 5, 20, 0),
    )
    assert created.status_code == 201
    response = client.delete(f"/api/reservations/{created.json()['id']}", headers=headers)
    assert response.status_code == 400
    assert "이미 시작된 예약" in response.json()["detail"]


def test_아직_시작하지_않은_예약은_조기_종료할_수_없다(client, headers, short_gpu, existing):
    response = client.post(f"/api/reservations/{existing['id']}/end-now", headers=headers)
    assert response.status_code == 400
    assert "아직 시작하지 않은" in response.json()["detail"]


def test_남의_예약은_취소할_수_없다(client, other_headers, existing):
    response = client.delete(f"/api/reservations/{existing['id']}", headers=other_headers)
    assert response.status_code == 403
