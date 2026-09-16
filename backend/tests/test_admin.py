"""관리자 API 테스트 (Phase 4).

핵심은 PLAN 5장의 표다.
- 중복(겹침) 검사는 관리자에게도 **예외 없이** 적용된다 → 409
- 길이 제한·14일 범위 제한은 **관리자만** 무시할 수 있고, 무시하면 경고가 함께 온다
- 같은 요청을 일반 사용자가 하면 400 으로 거부된다

현재 시각은 모두 2026-01-05 14:20 으로 고정되어 있다(conftest.py 의 clock).
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from tests.conftest import (
    admin_headers,
    auth_headers,
    create_reservation,
    gpu_id_by,
    iso,
)


@pytest.fixture
def 관리자(client):
    return admin_headers(client)


@pytest.fixture
def 사용자(client):
    return auth_headers(client, email="user@example.com", name="홍길동")


@pytest.fixture
def short_gpu(client, 사용자):
    return gpu_id_by(client, 사용자, "short")


@pytest.fixture
def 예약(client, 사용자, short_gpu, clock):
    """일반 사용자가 만든 미래 예약. 내일 14시 ~ 18시."""
    response = create_reservation(
        client, 사용자, short_gpu, clock.hour(24), clock.hour(28)
    )
    assert response.status_code == 201, response.text
    return response.json()


def patch_time(client, headers, reservation_id, start, end):
    return client.patch(
        f"/api/admin/reservations/{reservation_id}",
        headers=headers,
        json={"start_at": iso(start), "end_at": iso(end)},
    )


# ---------- 목록 ----------

def test_관리자는_남이_만든_예약도_전부_볼_수_있다(client, 관리자, 예약):
    response = client.get("/api/admin/reservations", headers=관리자)
    assert response.status_code == 200
    목록 = response.json()
    assert [r["id"] for r in 목록] == [예약["id"]]
    # 누구 예약인지 구분할 수 있게 이름·이메일이 함께 온다
    assert 목록[0]["user_name"] == "홍길동"
    assert 목록[0]["user_email"] == "user@example.com"


def test_관리자_목록은_취소된_예약도_볼_수_있다(client, 관리자, 사용자, 예약):
    assert client.delete(f"/api/reservations/{예약['id']}", headers=사용자).status_code == 200

    전체 = client.get("/api/admin/reservations", headers=관리자, params={"status": "all"})
    assert [r["id"] for r in 전체.json()] == [예약["id"]]

    유효 = client.get("/api/admin/reservations", headers=관리자, params={"status": "active"})
    assert 유효.json() == []

    취소됨 = client.get(
        "/api/admin/reservations", headers=관리자, params={"status": "cancelled"}
    )
    assert [r["id"] for r in 취소됨.json()] == [예약["id"]]


def test_지난_예약만_빼고_볼_수_있다(client, 관리자, 사용자, short_gpu, clock, 예약):
    """period=current 는 아직 끝나지 않은 예약만 준다."""
    # 지금 진행 중인 예약 하나 더 (14:00 ~ 16:00)
    현재 = create_reservation(client, 사용자, short_gpu, clock.hour(0), clock.hour(2))
    assert 현재.status_code == 201

    # 시계를 사흘 뒤로 돌리면 두 예약 모두 지난 예약이 된다
    clock.set(clock.now + timedelta(days=3))
    응답 = client.get("/api/admin/reservations", headers=관리자, params={"period": "current"})
    assert 응답.json() == []

    응답 = client.get("/api/admin/reservations", headers=관리자, params={"period": "all"})
    assert len(응답.json()) == 2


# ---------- 수정: 중복은 관리자도 예외 없음 ----------

def test_관리자_수정이_다른_예약과_겹치면_거부된다(
    client, 관리자, 사용자, short_gpu, clock, 예약
):
    # 같은 GPU에 이어지는 다른 예약 (내일 18시 ~ 22시)
    옆예약 = create_reservation(client, 사용자, short_gpu, clock.hour(28), clock.hour(32))
    assert 옆예약.status_code == 201

    # 첫 예약의 종료를 20시까지 늘리면 옆 예약과 2시간 겹친다
    response = patch_time(client, 관리자, 예약["id"], clock.hour(24), clock.hour(30))
    assert response.status_code == 409
    assert "이미 예약된 시간" in response.json()["detail"]

    # 거부됐으니 원래 시간 그대로여야 한다
    확인 = client.get("/api/reservations/me", headers=사용자).json()
    그대로 = next(r for r in 확인 if r["id"] == 예약["id"])
    assert 그대로["end_at"] == iso(clock.hour(28))


def test_경계가_맞닿는_수정은_허용된다(client, 관리자, 사용자, short_gpu, clock, 예약):
    """18시 종료 ↔ 18시 시작은 겹치는 게 아니다 (SPEC 5장)."""
    옆예약 = create_reservation(client, 사용자, short_gpu, clock.hour(28), clock.hour(32))
    assert 옆예약.status_code == 201

    response = patch_time(client, 관리자, 예약["id"], clock.hour(25), clock.hour(28))
    assert response.status_code == 200, response.text
    assert response.json()["warnings"] == []


def test_수정할_때_자기_자신과는_겹침_판정을_하지_않는다(client, 관리자, 예약, clock):
    """원래 시간과 겹치는 범위로 줄이거나 늘리는 것은 정상 동작이어야 한다."""
    response = patch_time(client, 관리자, 예약["id"], clock.hour(25), clock.hour(27))
    assert response.status_code == 200, response.text
    assert response.json()["reservation"]["start_at"] == iso(clock.hour(25))
    assert response.json()["reservation"]["end_at"] == iso(clock.hour(27))


# ---------- 수정: 길이·14일 제한은 관리자만 무시 가능 ----------

def test_관리자는_단주기를_100시간으로_늘릴_수_있고_경고가_온다(client, 관리자, 예약, clock):
    response = patch_time(client, 관리자, 예약["id"], clock.hour(24), clock.hour(124))
    assert response.status_code == 200, response.text
    결과 = response.json()
    assert 결과["reservation"]["end_at"] == iso(clock.hour(124))
    assert any("단주기" in w and "무시" in w for w in 결과["warnings"])


def test_일반_사용자는_단주기를_100시간으로_예약할_수_없다(
    client, 사용자, short_gpu, clock
):
    """같은 길이를 일반 사용자가 신청하면 400 으로 거부된다 (관리자에게만 완화)."""
    response = create_reservation(
        client, 사용자, short_gpu, clock.hour(48), clock.hour(148)
    )
    assert response.status_code == 400
    assert "최대 48시간" in response.json()["detail"]


def test_관리자는_20일_뒤_시작으로_바꿀_수_있고_경고가_온다(client, 관리자, 예약, clock):
    시작 = clock.hour(24 * 20)
    response = patch_time(client, 관리자, 예약["id"], 시작, 시작 + timedelta(hours=4))
    assert response.status_code == 200, response.text
    결과 = response.json()
    assert 결과["reservation"]["start_at"] == iso(시작)
    assert any("14일" in w for w in 결과["warnings"])


def test_일반_사용자는_20일_뒤를_예약할_수_없다(client, 사용자, short_gpu, clock):
    시작 = clock.hour(24 * 20)
    response = create_reservation(client, 사용자, short_gpu, 시작, 시작 + timedelta(hours=4))
    assert response.status_code == 400
    assert "14일" in response.json()["detail"]


def test_규칙을_지킨_수정에는_경고가_없다(client, 관리자, 예약, clock):
    response = patch_time(client, 관리자, 예약["id"], clock.hour(26), clock.hour(30))
    assert response.status_code == 200, response.text
    assert response.json()["warnings"] == []


# ---------- 수정: 관리자도 못 어기는 규칙 ----------

def test_관리자도_정시가_아니면_수정할_수_없다(client, 관리자, 예약, clock):
    response = patch_time(
        client, 관리자, 예약["id"], clock.hour(24) + timedelta(minutes=30), clock.hour(28)
    )
    assert response.status_code == 400
    assert "정시" in response.json()["detail"]


def test_관리자도_종료가_시작보다_앞설_수_없다(client, 관리자, 예약, clock):
    response = patch_time(client, 관리자, 예약["id"], clock.hour(28), clock.hour(24))
    assert response.status_code == 400
    assert "종료 시각" in response.json()["detail"]


def test_관리자도_지난_시간으로는_옮길_수_없다(client, 관리자, 예약, clock):
    response = patch_time(client, 관리자, 예약["id"], clock.hour(-3), clock.hour(2))
    assert response.status_code == 400
    assert "지난 시간" in response.json()["detail"]


def test_취소된_예약은_수정할_수_없다(client, 관리자, 사용자, 예약, clock):
    assert client.delete(f"/api/reservations/{예약['id']}", headers=사용자).status_code == 200
    response = patch_time(client, 관리자, 예약["id"], clock.hour(26), clock.hour(30))
    assert response.status_code == 400
    assert "취소된 예약" in response.json()["detail"]


def test_없는_예약을_수정하면_404(client, 관리자, clock):
    response = patch_time(client, 관리자, 99999, clock.hour(26), clock.hour(30))
    assert response.status_code == 404


# ---------- 삭제(강제 취소) ----------

def test_관리자는_이미_시작된_예약도_취소할_수_있다(
    client, 관리자, 사용자, short_gpu, clock
):
    """본인도 취소할 수 없는 '사용 중' 예약을 관리자는 강제로 취소할 수 있다."""
    사용중 = create_reservation(client, 사용자, short_gpu, clock.hour(0), clock.hour(6))
    assert 사용중.status_code == 201
    예약id = 사용중.json()["id"]

    # 본인은 거부됨
    assert client.delete(f"/api/reservations/{예약id}", headers=사용자).status_code == 400

    response = client.delete(f"/api/admin/reservations/{예약id}", headers=관리자)
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"

    # 취소했으니 그 시간대를 다른 사람이 다시 예약할 수 있어야 한다
    다시 = create_reservation(client, 사용자, short_gpu, clock.hour(1), clock.hour(5))
    assert 다시.status_code == 201, 다시.text


def test_관리자가_같은_예약을_두_번_삭제하면_400(client, 관리자, 예약):
    assert client.delete(f"/api/admin/reservations/{예약['id']}", headers=관리자).status_code == 200
    다시 = client.delete(f"/api/admin/reservations/{예약['id']}", headers=관리자)
    assert 다시.status_code == 400
