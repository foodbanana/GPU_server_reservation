"""관리자 API 테스트 (Phase 4).

핵심은 PLAN 5장의 표다.
- 중복(겹침) 검사는 관리자에게도 **예외 없이** 적용된다 → 409
- 예약 길이 제한과 '14일 이내 시작' 제한이 없어졌으므로 '관리자만 무시할 수 있는
  규칙'도 없다. 정시·순서·지난 시각 검사는 관리자에게도 그대로 적용된다.
- 가입자 목록은 관리자만 볼 수 있고, 비밀번호 해시는 절대 응답에 담기지 않는다.

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
    assert response.json()["end_at"] == iso(clock.hour(28))


def test_수정할_때_자기_자신과는_겹침_판정을_하지_않는다(client, 관리자, 예약, clock):
    """원래 시간과 겹치는 범위로 줄이거나 늘리는 것은 정상 동작이어야 한다."""
    response = patch_time(client, 관리자, 예약["id"], clock.hour(25), clock.hour(27))
    assert response.status_code == 200, response.text
    assert response.json()["start_at"] == iso(clock.hour(25))
    assert response.json()["end_at"] == iso(clock.hour(27))


# ---------- 수정: 길이·기간 제한이 없어졌다 ----------
# 예전에는 관리자만 무시할 수 있던 제한들이다. 이제는 누구에게도 적용되지 않는다.

def test_관리자는_단주기를_100시간으로_늘릴_수_있다(client, 관리자, 예약, clock):
    response = patch_time(client, 관리자, 예약["id"], clock.hour(24), clock.hour(124))
    assert response.status_code == 200, response.text
    결과 = response.json()
    assert 결과["end_at"] == iso(clock.hour(124))
    # 무시할 규칙이 없으므로 경고 자체가 응답에서 사라졌다
    assert "warnings" not in 결과


def test_일반_사용자도_단주기를_100시간으로_예약할_수_있다(
    client, 사용자, short_gpu, clock
):
    """예전에는 400으로 거부됐지만, 이제 길이 제한이 없으므로 그대로 만들어진다."""
    response = create_reservation(
        client, 사용자, short_gpu, clock.hour(200), clock.hour(300)
    )
    assert response.status_code == 201, response.text


def test_관리자는_20일_뒤_시작으로_바꿀_수_있다(client, 관리자, 예약, clock):
    시작 = clock.hour(24 * 20)
    response = patch_time(client, 관리자, 예약["id"], 시작, 시작 + timedelta(hours=4))
    assert response.status_code == 200, response.text
    assert response.json()["start_at"] == iso(시작)


def test_일반_사용자도_20일_뒤를_예약할_수_있다(client, 사용자, short_gpu, clock):
    시작 = clock.hour(24 * 20)
    response = create_reservation(client, 사용자, short_gpu, 시작, 시작 + timedelta(hours=4))
    assert response.status_code == 201, response.text


# ---------- 수정: 사용 중인 예약의 종료 시각만 바꾸기 ----------
# 시작 시각을 그대로 두면 '지난 시각' 검사를 건너뛴다.
# 그래야 지금 돌고 있는 예약을 관리자가 연장해 줄 수 있다.
#
# 아래 테스트가 진짜 의미를 가지려면 예약의 시작 시각이 **현재 정시보다 앞서** 있어야 한다.
# (시작이 마침 현재 정시와 같으면 원래 규칙으로도 통과하므로 아무것도 확인하지 못한다)
# 그래서 픽스처가 예약을 만든 뒤 시계를 3시간 앞으로 돌린다.

@pytest.fixture
def 사용중예약(client, 사용자, short_gpu, clock):
    """세 시간 전에 시작해서 지금 돌고 있는 예약.

    14:00 ~ 20:00 으로 만든 뒤 시계를 3시간 돌려 지금을 17:20 으로 만든다.
    따라서 이 예약의 시작(14:00)은 '이미 지난 시각'이고,
    그 뒤로 clock.hour(0) 은 17:00, 예약의 시작은 clock.hour(-3) 이다.
    """
    response = create_reservation(client, 사용자, short_gpu, clock.hour(0), clock.hour(6))
    assert response.status_code == 201, response.text
    body = response.json()
    clock.set(clock.now + timedelta(hours=3))
    return body


def 원래시작(clock):
    """사용중예약 의 시작 시각 (시계를 돌린 뒤 기준으로 3시간 전)."""
    return clock.hour(-3)


def test_관리자는_사용중인_예약의_종료를_늘릴_수_있다(client, 관리자, 사용중예약, clock):
    """시작(세 시간 전)은 그대로 두고 종료만 20:00 → 다음날 20:00 으로 연장."""
    response = patch_time(client, 관리자, 사용중예약["id"], 원래시작(clock), clock.hour(27))
    assert response.status_code == 200, response.text
    결과 = response.json()
    assert 결과["start_at"] == iso(원래시작(clock))  # 시작은 그대로
    assert 결과["end_at"] == iso(clock.hour(27))


def test_관리자는_사용중인_예약의_종료를_줄일_수_있다(client, 관리자, 사용중예약, clock):
    """종료를 앞당겨 남은 시간을 반납시킬 수도 있다 (조기 종료를 관리자가 대신)."""
    response = patch_time(client, 관리자, 사용중예약["id"], 원래시작(clock), clock.hour(1))
    assert response.status_code == 200, response.text
    assert response.json()["end_at"] == iso(clock.hour(1))


def test_연장한_시간은_다른_사람이_예약할_수_없다(
    client, 관리자, 사용자, short_gpu, clock, 사용중예약
):
    """연장이 진짜로 저장됐는지 겹침으로 확인한다."""
    assert patch_time(
        client, 관리자, 사용중예약["id"], 원래시작(clock), clock.hour(27)
    ).status_code == 200

    막힘 = create_reservation(client, 사용자, short_gpu, clock.hour(10), clock.hour(12))
    assert 막힘.status_code == 409


def test_연장이_옆_예약과_겹치면_거부된다(
    client, 관리자, 사용자, short_gpu, clock, 사용중예약
):
    """사용 중인 예약이라도 겹침은 예외 없이 막는다."""
    옆예약 = create_reservation(client, 사용자, short_gpu, clock.hour(5), clock.hour(9))
    assert 옆예약.status_code == 201

    response = patch_time(client, 관리자, 사용중예약["id"], 원래시작(clock), clock.hour(7))
    assert response.status_code == 409
    assert "이미 예약된 시간" in response.json()["detail"]


def test_사용중인_예약의_시작_시각을_옮기려_하면_거부된다(client, 관리자, 사용중예약, clock):
    """봐 주는 것은 '시작을 건드리지 않는 수정' 뿐이다. 시작을 옮기면 그대로 400."""
    response = patch_time(client, 관리자, 사용중예약["id"], clock.hour(-5), clock.hour(3))
    assert response.status_code == 400
    assert "지난 시간" in response.json()["detail"]


def test_종료를_지난_시간으로_바꾸면_거부된다(client, 관리자, 사용중예약, clock):
    """시작은 그대로여도 종료까지 과거로 보내는 것은 막는다. (16:00 은 이미 지났다)"""
    response = patch_time(client, 관리자, 사용중예약["id"], 원래시작(clock), clock.hour(-1))
    assert response.status_code == 400
    assert "종료 시각을 지난 시간으로" in response.json()["detail"]


def test_이미_끝난_예약도_종료를_미래로_늘리면_되살릴_수_있다(
    client, 관리자, 사용자, short_gpu, clock
):
    """어제 끝난 예약의 종료만 미래로 늘리는 경우 (시작은 그대로)."""
    예약 = create_reservation(client, 사용자, short_gpu, clock.hour(0), clock.hour(2))
    assert 예약.status_code == 201
    clock.set(clock.now + timedelta(days=1))  # 하루 뒤 — 그 예약은 이미 끝났다

    response = patch_time(client, 관리자, 예약.json()["id"], clock.hour(-24), clock.hour(3))
    assert response.status_code == 200, response.text
    assert response.json()["end_at"] == iso(clock.hour(3))


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


# ---------- 가입자 목록 (보기 전용) ----------

def test_관리자는_가입자_목록을_볼_수_있다(client, 관리자, 사용자, 예약):
    response = client.get("/api/admin/users", headers=관리자)
    assert response.status_code == 200, response.text
    목록 = response.json()

    # 가입 순서대로: 관리자 픽스처가 먼저 가입하고 그다음 일반 사용자
    assert [u["email"] for u in 목록] == ["admin@example.com", "user@example.com"]

    관리자행, 사용자행 = 목록
    assert 관리자행["name"] == "관리자" and 관리자행["is_admin"] is True
    assert 사용자행["name"] == "홍길동" and 사용자행["is_admin"] is False

    # 가입일이 한국 시간(+09:00)으로 온다
    assert 사용자행["created_at"].endswith("+09:00")

    # 현재·예정 예약 개수
    assert 사용자행["active_reservation_count"] == 1
    assert 관리자행["active_reservation_count"] == 0


def test_가입자_목록에_비밀번호_해시가_들어가지_않는다(client, 관리자, 사용자):
    response = client.get("/api/admin/users", headers=관리자)
    assert response.status_code == 200
    본문 = response.text
    assert "password" not in 본문 and "hash" not in 본문 and "$2b$" not in 본문
    for user in response.json():
        assert set(user) == {
            "id",
            "name",
            "email",
            "is_admin",
            "created_at",
            "active_reservation_count",
        }


def test_예약_개수는_취소되거나_끝난_예약을_빼고_센다(
    client, 관리자, 사용자, short_gpu, clock, 예약
):
    # 취소한 예약은 세지 않는다
    취소할것 = create_reservation(client, 사용자, short_gpu, clock.hour(40), clock.hour(44))
    assert 취소할것.status_code == 201
    assert client.delete(
        f"/api/reservations/{취소할것.json()['id']}", headers=사용자
    ).status_code == 200

    def 개수():
        목록 = client.get("/api/admin/users", headers=관리자).json()
        return next(u["active_reservation_count"] for u in 목록 if u["email"] == "user@example.com")

    assert 개수() == 1  # 픽스처 예약 하나만 남는다

    # 시계를 사흘 뒤로 돌리면 그 예약도 '끝난 예약'이 되어 0이 된다
    clock.set(clock.now + timedelta(days=3))
    assert 개수() == 0


def test_일반_사용자는_가입자_목록을_볼_수_없다(client, 사용자):
    response = client.get("/api/admin/users", headers=사용자)
    assert response.status_code == 403
    assert "관리자" in response.json()["detail"]


def test_로그인하지_않으면_가입자_목록은_401(client):
    assert client.get("/api/admin/users").status_code == 401
