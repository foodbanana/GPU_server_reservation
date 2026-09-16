"""예약 규칙 검사 테스트 (PLAN 5장 표의 1~5번).

현재 시각은 모두 2026-01-05 14:20 으로 고정되어 있다(conftest.py 의 clock).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from tests.conftest import auth_headers, create_reservation, gpu_id_by, iso


@pytest.fixture
def headers(client):
    return auth_headers(client, email="rule@example.com")


@pytest.fixture
def short_gpu(client, headers):
    return gpu_id_by(client, headers, "short")


@pytest.fixture
def long_gpu(client, headers):
    return gpu_id_by(client, headers, "long")


# ---------- 1. 정시(분·초 0) 검사 ----------

def test_정시가_아니면_거부된다(client, headers, short_gpu, clock):
    response = create_reservation(
        client, headers, short_gpu, clock.hour(1) + timedelta(minutes=30), clock.hour(3)
    )
    assert response.status_code == 400
    assert "정시" in response.json()["detail"]


# ---------- 2. 종료 > 시작 검사 ----------

@pytest.mark.parametrize("end_offset", [1, 0])  # 시작보다 앞, 시작과 같음
def test_종료가_시작보다_뒤가_아니면_거부된다(client, headers, short_gpu, clock, end_offset):
    response = create_reservation(
        client, headers, short_gpu, clock.hour(5), clock.hour(5 - end_offset)
    )
    assert response.status_code == 400
    assert "종료 시각은 시작 시각보다 뒤" in response.json()["detail"]


# ---------- 3. 시작 시각은 '현재 시각 정시 내림' 이상 ----------
# 지금이 14:20이므로 14:00 시작은 허용, 13:00 시작은 거부

def test_현재_시각이_속한_정시_시작은_허용된다(client, headers, short_gpu, clock):
    assert clock.now == datetime(2026, 1, 5, 14, 20)
    response = create_reservation(
        client,
        headers,
        short_gpu,
        datetime(2026, 1, 5, 14, 0),  # 14:00 = 지금(14:20)이 속한 정시
        datetime(2026, 1, 5, 18, 0),
    )
    assert response.status_code == 201, response.text
    assert response.json()["start_at"] == iso(datetime(2026, 1, 5, 14, 0))


def test_한_시간_전_시작은_거부된다(client, headers, short_gpu, clock):
    response = create_reservation(
        client,
        headers,
        short_gpu,
        datetime(2026, 1, 5, 13, 0),  # 13:00 = 이미 지난 시간
        datetime(2026, 1, 5, 18, 0),
    )
    assert response.status_code == 400
    assert "지난 시간은 예약할 수 없습니다" in response.json()["detail"]


# ---------- 4. 14일 이내 검사 ----------

def test_정확히_14일_뒤_시작은_허용된다(client, headers, short_gpu, clock):
    start = clock.hour(24 * 14)
    response = create_reservation(client, headers, short_gpu, start, start + timedelta(hours=2))
    assert response.status_code == 201, response.text


def test_14일을_넘긴_시작은_거부된다(client, headers, short_gpu, clock):
    start = clock.hour(24 * 14 + 1)
    response = create_reservation(client, headers, short_gpu, start, start + timedelta(hours=2))
    assert response.status_code == 400
    assert "14일 이내" in response.json()["detail"]


# ---------- 5. 단주기 / 장주기 시간 길이 규칙 ----------
# 단주기: 최소 1시간, 최대 48시간

@pytest.mark.parametrize("hours", [1, 24, 48])
def test_단주기_허용_범위는_통과한다(client, headers, short_gpu, clock, hours):
    start = clock.hour(1)
    response = create_reservation(client, headers, short_gpu, start, start + timedelta(hours=hours))
    assert response.status_code == 201, response.text


def test_단주기_49시간은_거부된다(client, headers, short_gpu, clock):
    start = clock.hour(1)
    response = create_reservation(client, headers, short_gpu, start, start + timedelta(hours=49))
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "단주기" in detail and "48시간" in detail


# 장주기: 최소 48시간, 최대 336시간(14일)

@pytest.mark.parametrize("hours", [48, 200, 336])
def test_장주기_허용_범위는_통과한다(client, headers, long_gpu, clock, hours):
    start = clock.hour(1)
    response = create_reservation(client, headers, long_gpu, start, start + timedelta(hours=hours))
    assert response.status_code == 201, response.text


@pytest.mark.parametrize("hours", [1, 24, 47])
def test_장주기_48시간_미만은_거부된다(client, headers, long_gpu, clock, hours):
    start = clock.hour(1)
    response = create_reservation(client, headers, long_gpu, start, start + timedelta(hours=hours))
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "장주기" in detail and "48시간" in detail


def test_48시간은_단주기_장주기_양쪽에서_모두_허용된다(client, headers, short_gpu, long_gpu, clock):
    """단주기 최대(48h)와 장주기 최소(48h)가 맞닿아 있으므로 둘 다 통과해야 한다."""
    start = clock.hour(1)
    end = start + timedelta(hours=48)
    assert create_reservation(client, headers, short_gpu, start, end).status_code == 201
    assert create_reservation(client, headers, long_gpu, start, end).status_code == 201


def test_장주기_337시간은_거부된다(client, headers, long_gpu, clock):
    start = clock.hour(1)
    response = create_reservation(client, headers, long_gpu, start, start + timedelta(hours=337))
    assert response.status_code == 400
    assert "336시간" in response.json()["detail"]


def test_단주기_규칙이_장주기_GPU에_적용되지_않는다(client, headers, long_gpu, clock):
    """단주기라면 통과했을 2시간짜리가 장주기 GPU에서는 거부되어야 한다."""
    start = clock.hour(1)
    response = create_reservation(client, headers, long_gpu, start, start + timedelta(hours=2))
    assert response.status_code == 400


# ---------- 기타 ----------

def test_없는_GPU는_404(client, headers, clock):
    start = clock.hour(1)
    response = create_reservation(client, headers, 9999, start, start + timedelta(hours=2))
    assert response.status_code == 404


def test_설정값_조회(client):
    response = client.get("/api/config")
    assert response.status_code == 200
    body = response.json()
    assert body["timezone"] == "Asia/Seoul"
    assert body["short"] == {"min_hours": 1, "max_hours": 48}
    assert body["long"] == {"min_hours": 48, "max_hours": 336}
    assert body["booking_horizon_days"] == 14


def test_GPU는_단주기_6개_장주기_6개(client, headers):
    gpus = client.get("/api/gpus", headers=headers).json()
    assert len(gpus) == 12
    assert sum(1 for g in gpus if g["category"] == "short") == 6
    assert sum(1 for g in gpus if g["category"] == "long") == 6
    # 타임라인 행 순서: 단주기 6개가 먼저 온다
    assert [g["category"] for g in gpus] == ["short"] * 6 + ["long"] * 6
