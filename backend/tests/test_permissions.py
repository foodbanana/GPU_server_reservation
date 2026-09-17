"""권한 테스트 (Phase 4).

"일반 사용자는 남의 예약을 건드릴 수 없다"가 이 파일의 핵심이다.
현재 시각은 모두 2026-01-05 14:20 으로 고정되어 있다(conftest.py 의 clock).
"""

from __future__ import annotations

import pytest

from tests.conftest import (
    admin_headers,
    auth_headers,
    create_reservation,
    gpu_id_by,
    iso,
)


@pytest.fixture
def 주인(client):
    """예약을 만든 사람."""
    return auth_headers(client, email="owner@example.com", name="예약주인")


@pytest.fixture
def 남(client):
    """관계없는 다른 일반 사용자."""
    return auth_headers(client, email="other@example.com", name="딴사람")


@pytest.fixture
def 관리자(client):
    return admin_headers(client)


@pytest.fixture
def short_gpu(client, 주인):
    return gpu_id_by(client, 주인, "short")


@pytest.fixture
def 미래예약(client, 주인, short_gpu, clock):
    """아직 시작하지 않은 예약 (내일 쯤)."""
    response = create_reservation(
        client, 주인, short_gpu, clock.hour(24), clock.hour(28)
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def 사용중예약(client, 주인, short_gpu, clock):
    """지금 사용 중인 예약 (14:00 시작 ~ 20:00 종료, 지금은 14:20)."""
    response = create_reservation(
        client, 주인, short_gpu, clock.hour(0), clock.hour(6)
    )
    assert response.status_code == 201, response.text
    return response.json()


# ---------- 남의 예약은 건드릴 수 없다 ----------

def test_남의_예약은_취소할_수_없다(client, 남, 미래예약, clock):
    response = client.delete(f"/api/reservations/{미래예약['id']}", headers=남)
    assert response.status_code == 403
    assert "본인" in response.json()["detail"]

    # 거부만 하고 끝난 게 아니라, 예약이 정말 그대로 남아 있는지 확인한다
    확인 = client.get(
        "/api/reservations",
        headers=남,
        params={"start": iso(clock.hour(0)), "end": iso(clock.hour(24 * 14))},
    )
    assert 확인.status_code == 200
    assert any(r["id"] == 미래예약["id"] for r in 확인.json())


def test_남의_예약은_조기_종료할_수_없다(client, 남, 사용중예약):
    response = client.post(
        f"/api/reservations/{사용중예약['id']}/end-now", headers=남
    )
    assert response.status_code == 403


def test_남의_예약은_수정할_수_없다(client, 남, 미래예약, clock):
    """일반 사용자는 관리자 수정 API 자체에 접근할 수 없다."""
    response = client.patch(
        f"/api/admin/reservations/{미래예약['id']}",
        headers=남,
        json={"start_at": iso(clock.hour(30)), "end_at": iso(clock.hour(32))},
    )
    assert response.status_code == 403
    assert "관리자" in response.json()["detail"]


def test_일반_사용자는_관리자_목록을_볼_수_없다(client, 남):
    response = client.get("/api/admin/reservations", headers=남)
    assert response.status_code == 403


def test_일반_사용자는_가입자_목록을_볼_수_없다(client, 남):
    """가입자 목록은 관리자 전용이다. 주소를 직접 불러도 403."""
    response = client.get("/api/admin/users", headers=남)
    assert response.status_code == 403
    assert "관리자" in response.json()["detail"]


def test_일반_사용자는_관리자_삭제를_할_수_없다(client, 남, 미래예약):
    response = client.delete(f"/api/admin/reservations/{미래예약['id']}", headers=남)
    assert response.status_code == 403


def test_로그인하지_않으면_관리자_API는_401(client):
    response = client.get("/api/admin/reservations")
    assert response.status_code == 401


# ---------- 본인 예약은 할 수 있다 ----------

def test_본인_예약은_취소할_수_있다(client, 주인, 미래예약):
    response = client.delete(f"/api/reservations/{미래예약['id']}", headers=주인)
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_본인의_사용중_예약은_조기_종료할_수_있다(client, 주인, 사용중예약, clock):
    response = client.post(
        f"/api/reservations/{사용중예약['id']}/end-now", headers=주인
    )
    assert response.status_code == 200
    # 14:20 이므로 종료 시각이 15:00(정시 올림)으로 당겨진다
    assert response.json()["end_at"] == iso(clock.hour(1))


def test_내_예약_목록에는_내_것만_나온다(client, 주인, 남, 미래예약):
    response = client.get("/api/reservations/me", headers=남)
    assert response.status_code == 200
    assert response.json() == []

    response = client.get("/api/reservations/me", headers=주인)
    assert [r["id"] for r in response.json()] == [미래예약["id"]]


# ---------- 시작된 예약은 취소할 수 없다 ----------

def test_이미_시작된_예약은_취소할_수_없다(client, 주인, 사용중예약):
    response = client.delete(f"/api/reservations/{사용중예약['id']}", headers=주인)
    assert response.status_code == 400
    assert "이미 시작된 예약" in response.json()["detail"]


def test_아직_시작하지_않은_예약은_조기_종료할_수_없다(client, 주인, 미래예약):
    response = client.post(
        f"/api/reservations/{미래예약['id']}/end-now", headers=주인
    )
    assert response.status_code == 400
    assert "아직 시작하지 않은" in response.json()["detail"]


def test_이미_취소한_예약은_다시_취소할_수_없다(client, 주인, 미래예약):
    assert client.delete(f"/api/reservations/{미래예약['id']}", headers=주인).status_code == 200
    다시 = client.delete(f"/api/reservations/{미래예약['id']}", headers=주인)
    assert 다시.status_code == 400
    assert "이미 취소된" in 다시.json()["detail"]


# ---------- 관리자는 남의 예약도 건드릴 수 있다 ----------

def test_관리자는_남의_예약을_취소할_수_있다(client, 관리자, 미래예약):
    response = client.delete(f"/api/reservations/{미래예약['id']}", headers=관리자)
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_관리자는_남의_사용중_예약을_조기_종료할_수_있다(client, 관리자, 사용중예약):
    response = client.post(
        f"/api/reservations/{사용중예약['id']}/end-now", headers=관리자
    )
    assert response.status_code == 200
