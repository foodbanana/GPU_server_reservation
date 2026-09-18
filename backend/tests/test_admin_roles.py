"""관리자 화면에서 관리자 권한을 주고 빼는 기능 (PATCH /api/admin/users/role).

터미널의 scripts/set_admin.py 와 같은 규칙을 웹으로 연 것이라,
'마지막 남은 관리자 보호' 같은 기존 규칙이 웹에서도 똑같이 지켜지는지 확인한다.

웹에만 있는 규칙 두 가지도 여기서 확인한다.
- 최고 관리자(환경변수 GPU_RESERVE_SUPER_ADMIN_EMAIL) 는 아무도 해제할 수 없다
- 자기 자신은 해제할 수 없다

현재 시각은 2026-01-05 14:20 으로 고정되어 있다(conftest.py 의 clock).
"""

from __future__ import annotations

import pytest

from app.services import accounts
from tests.conftest import admin_headers, auth_headers, login_headers, signup

슈퍼관리자이메일 = "super@example.com"


# ---------- 도우미 ----------

def 권한바꾸기(client, headers, *, is_admin: bool, user_id=None, email=None):
    본문 = {"is_admin": is_admin}
    if user_id is not None:
        본문["user_id"] = user_id
    if email is not None:
        본문["email"] = email
    return client.patch("/api/admin/users/role", headers=headers, json=본문)


def 목록(client, headers) -> list[dict]:
    response = client.get("/api/admin/users", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def 한사람(client, headers, email: str) -> dict:
    for u in 목록(client, headers):
        if u["email"] == email:
            return u
    raise AssertionError(f"{email} 을 목록에서 찾지 못했습니다.")


@pytest.fixture
def 관리자(client):
    """기본 관리자 (admin@example.com)."""
    return admin_headers(client)


@pytest.fixture
def 사용자(client):
    """일반 사용자 (user@example.com)."""
    return auth_headers(client, email="user@example.com", name="홍길동")


@pytest.fixture
def 슈퍼관리자보호켬(monkeypatch):
    """환경변수로 최고 관리자 이메일을 지정한 상태를 만든다."""
    monkeypatch.setenv(accounts.ENV_SUPER_ADMIN_EMAIL, 슈퍼관리자이메일)


# ---------- 승격 ----------

def test_관리자가_일반_사용자를_승격할_수_있다(client, 관리자, 사용자):
    대상 = 한사람(client, 관리자, "user@example.com")
    assert 대상["is_admin"] is False

    response = 권한바꾸기(client, 관리자, is_admin=True, user_id=대상["id"])

    assert response.status_code == 200, response.text
    본문 = response.json()
    assert 본문["result"] == "promoted"
    assert 본문["is_admin"] is True
    assert "다시 로그인" in 본문["message"]        # 재로그인 안내를 준다
    # 목록에도 곧바로 반영된다
    assert 한사람(client, 관리자, "user@example.com")["is_admin"] is True


def test_이메일로도_지정할_수_있다(client, 관리자, 사용자):
    response = 권한바꾸기(client, 관리자, is_admin=True, email="user@example.com")
    assert response.status_code == 200, response.text
    assert response.json()["result"] == "promoted"


def test_승격된_사람은_실제로_관리자_API를_쓸_수_있다(client, 관리자, 사용자):
    # 승격 전에는 막힌다
    assert client.get("/api/admin/users", headers=사용자).status_code == 403

    권한바꾸기(client, 관리자, is_admin=True, email="user@example.com")

    # 권한은 토큰이 아니라 DB를 보고 판단하므로 다시 로그인하지 않아도 통한다
    assert client.get("/api/admin/users", headers=사용자).status_code == 200


def test_이미_관리자를_또_승격해도_오류가_아니다(client, 관리자):
    response = 권한바꾸기(client, 관리자, is_admin=True, email="admin@example.com")
    assert response.status_code == 200
    assert response.json()["result"] == "already_admin"


# ---------- 해제 ----------

def test_다른_관리자를_해제할_수_있다(client, 관리자, 사용자):
    권한바꾸기(client, 관리자, is_admin=True, email="user@example.com")

    response = 권한바꾸기(client, 관리자, is_admin=False, email="user@example.com")

    assert response.status_code == 200, response.text
    assert response.json()["result"] == "revoked"
    assert 한사람(client, 관리자, "user@example.com")["is_admin"] is False
    # 해제된 사람은 관리자 API 에서 막힌다
    assert client.get("/api/admin/users", headers=사용자).status_code == 403


def test_원래_일반_사용자를_해제해도_오류가_아니다(client, 관리자, 사용자):
    response = 권한바꾸기(client, 관리자, is_admin=False, email="user@example.com")
    assert response.status_code == 200
    assert response.json()["result"] == "already_normal"


# ---------- 안전장치 1: 자기 자신 해제 금지 ----------

def test_자기_자신은_해제할_수_없다(client, 관리자, 사용자):
    # 관리자가 둘이어도(마지막 관리자 규칙에 걸리지 않아도) 본인 해제는 막는다
    권한바꾸기(client, 관리자, is_admin=True, email="user@example.com")

    response = 권한바꾸기(client, 관리자, is_admin=False, email="admin@example.com")

    assert response.status_code == 400
    assert "자기 자신" in response.json()["detail"]
    assert 한사람(client, 관리자, "admin@example.com")["is_admin"] is True


# ---------- 안전장치 2: 마지막 남은 관리자 보호 ----------

def test_관리자가_한_명만_남아도_해제할_수_없다(client, 관리자, 사용자):
    """관리자가 한 명뿐인 상황에서 그 사람을 해제하려는 모든 경로가 막히는지.

    웹에서는 '마지막 한 명'을 해제할 수 있는 사람이 그 사람 자신밖에 없으므로
    실제로는 '자기 자신 해제 금지'가 먼저 걸린다. 어느 규칙이 걸리든
    **관리자가 0명이 되는 일은 없어야 한다**는 것이 핵심이다.
    (규칙 자체는 아래 서비스 계층 테스트에서 따로 확인한다)
    """
    # 지금 관리자는 admin 한 명뿐이다
    assert [u["email"] for u in 목록(client, 관리자) if u["is_admin"]] == [
        "admin@example.com"
    ]

    response = 권한바꾸기(client, 관리자, is_admin=False, email="admin@example.com")

    assert response.status_code == 400
    # 관리자가 여전히 한 명 남아 있어야 한다
    assert [u["email"] for u in 목록(client, 관리자) if u["is_admin"]] == [
        "admin@example.com"
    ]


def test_마지막_관리자_보호는_서비스_계층에서도_지켜진다(db_session):
    """웹 규칙(본인 해제 금지)에 가려지지 않는 순수한 확인.

    actor 를 주지 않으면 '본인 해제 금지'는 건너뛰고 마지막 관리자 보호만 남는다.
    """
    from app.models import User
    from app.security import hash_password

    유일한관리자 = User(
        name="유일", email="only@example.com",
        password_hash=hash_password("pw"), is_admin=True,
    )
    db_session.add(유일한관리자)
    db_session.commit()

    with pytest.raises(accounts.AccountError, match="마지막 남은 관리자"):
        accounts.change_admin_status(
            db_session, target=유일한관리자, make_admin=False, actor=None
        )
    db_session.refresh(유일한관리자)
    assert 유일한관리자.is_admin is True


# ---------- 안전장치 3: 최고 관리자 보호 ----------

def test_최고_관리자는_다른_관리자가_해제할_수_없다(client, 관리자, 슈퍼관리자보호켬):
    signup(client, email=슈퍼관리자이메일, name="최고관리자")
    권한바꾸기(client, 관리자, is_admin=True, email=슈퍼관리자이메일)

    response = 권한바꾸기(client, 관리자, is_admin=False, email=슈퍼관리자이메일)

    assert response.status_code == 400
    assert "최고 관리자" in response.json()["detail"]
    assert 한사람(client, 관리자, 슈퍼관리자이메일)["is_admin"] is True


def test_최고_관리자는_본인도_해제할_수_없다(client, 관리자, 슈퍼관리자보호켬):
    """'본인 해제 금지'가 아니라 '최고 관리자' 규칙으로 막혀야 한다."""
    signup(client, email=슈퍼관리자이메일, name="최고관리자")
    권한바꾸기(client, 관리자, is_admin=True, email=슈퍼관리자이메일)
    최고관리자 = login_headers(client, 슈퍼관리자이메일)

    response = 권한바꾸기(client, 최고관리자, is_admin=False, email=슈퍼관리자이메일)

    assert response.status_code == 400
    assert "최고 관리자" in response.json()["detail"]
    assert 한사람(client, 관리자, 슈퍼관리자이메일)["is_admin"] is True


def test_최고_관리자_이메일은_대소문자와_공백을_무시한다(client, 관리자, monkeypatch):
    monkeypatch.setenv(accounts.ENV_SUPER_ADMIN_EMAIL, "  SUPER@Example.COM  ")
    signup(client, email=슈퍼관리자이메일, name="최고관리자")
    권한바꾸기(client, 관리자, is_admin=True, email=슈퍼관리자이메일)

    response = 권한바꾸기(client, 관리자, is_admin=False, email=슈퍼관리자이메일)
    assert response.status_code == 400
    assert "최고 관리자" in response.json()["detail"]


def test_환경변수가_없으면_최고_관리자_보호만_꺼지고_나머지는_동작한다(client, 관리자, monkeypatch):
    """배포에서 환경변수를 깜빡해도 기능 자체는 멀쩡해야 한다."""
    monkeypatch.delenv(accounts.ENV_SUPER_ADMIN_EMAIL, raising=False)
    signup(client, email=슈퍼관리자이메일, name="최고관리자")
    권한바꾸기(client, 관리자, is_admin=True, email=슈퍼관리자이메일)

    response = 권한바꾸기(client, 관리자, is_admin=False, email=슈퍼관리자이메일)

    assert response.status_code == 200
    assert response.json()["result"] == "revoked"


def test_환경변수가_비어_있어도_보호가_꺼진다(client, 관리자, monkeypatch):
    monkeypatch.setenv(accounts.ENV_SUPER_ADMIN_EMAIL, "   ")
    assert accounts.super_admin_email() is None
    assert accounts.is_super_admin_email(슈퍼관리자이메일) is False


def test_최고_관리자는_승격은_막히지_않는다(client, 관리자, 슈퍼관리자보호켬):
    """보호하는 것은 '해제'뿐이다. 관리자로 올리는 것은 정상 동작해야 한다."""
    signup(client, email=슈퍼관리자이메일, name="최고관리자")
    response = 권한바꾸기(client, 관리자, is_admin=True, email=슈퍼관리자이메일)
    assert response.status_code == 200
    assert response.json()["result"] == "promoted"


# ---------- 목록의 is_super_admin ----------

def test_목록이_최고_관리자를_표시해_준다(client, 관리자, 사용자, 슈퍼관리자보호켬):
    signup(client, email=슈퍼관리자이메일, name="최고관리자")

    assert 한사람(client, 관리자, 슈퍼관리자이메일)["is_super_admin"] is True
    assert 한사람(client, 관리자, "user@example.com")["is_super_admin"] is False
    assert 한사람(client, 관리자, "admin@example.com")["is_super_admin"] is False


def test_환경변수가_없으면_아무도_최고_관리자가_아니다(client, 관리자, 사용자, monkeypatch):
    monkeypatch.delenv(accounts.ENV_SUPER_ADMIN_EMAIL, raising=False)
    for u in 목록(client, 관리자):
        assert u["is_super_admin"] is False


# ---------- 권한 (일반 사용자 차단) ----------

def test_일반_사용자는_권한을_바꿀_수_없다(client, 관리자, 사용자):
    response = 권한바꾸기(client, 사용자, is_admin=True, email="user@example.com")
    assert response.status_code == 403
    # 정말로 안 바뀌었는지
    assert 한사람(client, 관리자, "user@example.com")["is_admin"] is False


def test_로그인하지_않으면_401(client, 관리자, 사용자):
    response = client.patch(
        "/api/admin/users/role", json={"is_admin": True, "email": "user@example.com"}
    )
    assert response.status_code == 401


# ---------- 잘못된 요청 ----------

def test_없는_user_id_면_404(client, 관리자):
    response = 권한바꾸기(client, 관리자, is_admin=True, user_id=999999)
    assert response.status_code == 404


def test_가입한_적_없는_이메일이면_404(client, 관리자):
    response = 권한바꾸기(client, 관리자, is_admin=True, email="nobody@example.com")
    assert response.status_code == 404
    assert "가입된 적 없는" in response.json()["detail"]


def test_대상을_둘_다_주거나_아예_안_주면_거부한다(client, 관리자, 사용자):
    대상 = 한사람(client, 관리자, "user@example.com")
    둘다 = 권한바꾸기(
        client, 관리자, is_admin=True, user_id=대상["id"], email="user@example.com"
    )
    없음 = 권한바꾸기(client, 관리자, is_admin=True)
    assert 둘다.status_code == 422
    assert 없음.status_code == 422
