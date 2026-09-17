"""예약 규칙 검사 테스트 (PLAN 5장 표).

남아 있는 규칙은 네 가지뿐이다.
  1. 정시(분·초 0)  2. 종료 > 시작  3. 지난 시각 금지  4. 같은 GPU 겹침 금지(test_overlap.py)

예약 길이 제한(단주기 최대·장주기 최소)과 '14일 이내 시작' 제한은 없앴으므로,
아래에는 "이제는 막히지 않는다"를 확인하는 테스트도 함께 둔다.
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


# ---------- 없어진 제한들: 이제는 막히지 않아야 한다 ----------
# 사람들끼리 협의해서 쓰기로 했으므로 길이·기간 제한을 모두 없앴다.

def test_14일을_넘긴_시작도_예약할_수_있다(client, headers, short_gpu, clock):
    start = clock.hour(24 * 60)  # 두 달 뒤
    response = create_reservation(client, headers, short_gpu, start, start + timedelta(hours=2))
    assert response.status_code == 201, response.text
    assert response.json()["start_at"] == iso(start)


@pytest.mark.parametrize("hours", [1, 48, 100, 336, 1000])
def test_단주기는_길이_제한_없이_예약된다(client, headers, short_gpu, clock, hours):
    start = clock.hour(1)
    response = create_reservation(client, headers, short_gpu, start, start + timedelta(hours=hours))
    assert response.status_code == 201, response.text


@pytest.mark.parametrize("hours", [1, 2, 47, 48, 500])
def test_장주기도_길이_제한_없이_예약된다(client, headers, long_gpu, clock, hours):
    """예전에는 장주기에 48시간 미만을 못 넣었지만 이제는 1시간도 된다."""
    start = clock.hour(1)
    response = create_reservation(client, headers, long_gpu, start, start + timedelta(hours=hours))
    assert response.status_code == 201, response.text


def test_단주기_장주기_구분은_그대로_남아_있다(client, headers):
    """규칙은 같아졌지만 분류(버튼·타임라인 그룹용)는 계속 구분된다."""
    gpus = client.get("/api/gpus", headers=headers).json()
    분류 = {g["category"] for g in gpus}
    assert 분류 == {"short", "long"}
    이름표 = {g["category"]: g["category_label"] for g in gpus}
    assert 이름표 == {"short": "단주기", "long": "장주기"}


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
    assert body["slot_minutes"] == 60
    # 타임라인이 한 번에 보여 주는 일수. 예약 가능 기간 제한이 아니다.
    assert body["timeline_days"] == 14
    # 길이 제한 설정은 응답에서 사라졌다
    assert "short" not in body and "long" not in body
    assert "booking_horizon_days" not in body


def test_GPU는_단주기_6개_장주기_6개(client, headers):
    gpus = client.get("/api/gpus", headers=headers).json()
    assert len(gpus) == 12
    assert sum(1 for g in gpus if g["category"] == "short") == 6
    assert sum(1 for g in gpus if g["category"] == "long") == 6
    # 타임라인 행 순서: 단주기 6개가 먼저 온다
    assert [g["category"] for g in gpus] == ["short"] * 6 + ["long"] * 6
