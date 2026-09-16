"""관리자 계정 스크립트가 쓰는 로직 테스트 (app/services/accounts.py).

scripts/create_admin.py 와 scripts/set_admin.py 는 '물어보고 출력하는 일'만 하고
판단은 전부 이 모듈이 하므로, 여기를 확인하면 두 명령어의 동작을 확인하는 셈이다.

확인하는 것:
- 이미 가입한 이메일이면 계정을 새로 만들지 않고 관리자로 올린다 (비밀번호·이름은 그대로)
- 마지막 남은 관리자의 권한은 해제할 수 없다
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import User
from app.security import hash_password, verify_password
from app.services import accounts
from tests.conftest import auth_headers, login_headers, signup


def 가입시키기(db, email: str, name: str = "홍길동", password: str = "test-pw-1234",
            is_admin: bool = False) -> User:
    """웹 회원가입으로 만들어진 계정과 같은 상태의 사용자를 하나 만든다."""
    user = User(
        name=name,
        email=email,
        password_hash=hash_password(password),
        is_admin=is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def 사용자수(db) -> int:
    return db.scalar(select(func.count()).select_from(User))


# ---------- create_admin: 새로 만들기 ----------

def test_없는_이메일이면_관리자_계정을_새로_만든다(db_session):
    결과, user = accounts.create_or_promote_admin(
        db_session, "new@example.com", name="새관리자", password="pw-1234"
    )
    assert 결과 == accounts.CREATED
    assert user.is_admin is True
    assert user.name == "새관리자"
    assert verify_password("pw-1234", user.password_hash)
    assert 사용자수(db_session) == 1


def test_이메일은_대소문자와_앞뒤_공백을_무시한다(db_session):
    accounts.create_or_promote_admin(
        db_session, "  Me@Example.COM ", name="관리자", password="pw-1234"
    )
    assert accounts.find_user(db_session, "me@example.com") is not None
    assert 사용자수(db_session) == 1


def test_새_계정인데_이름이_없으면_오류(db_session):
    with pytest.raises(accounts.AccountError, match="이름"):
        accounts.create_or_promote_admin(db_session, "new@example.com", password="pw-1234")
    assert 사용자수(db_session) == 0


def test_새_계정인데_비밀번호가_없으면_오류(db_session):
    with pytest.raises(accounts.AccountError, match="비밀번호"):
        accounts.create_or_promote_admin(db_session, "new@example.com", name="관리자")
    assert 사용자수(db_session) == 0


def test_비밀번호가_너무_길면_오류(db_session):
    with pytest.raises(accounts.AccountError, match="너무 깁니다"):
        accounts.create_or_promote_admin(
            db_session, "new@example.com", name="관리자", password="가" * 30
        )
    assert 사용자수(db_session) == 0


def test_이메일이_비어_있으면_오류(db_session):
    with pytest.raises(accounts.AccountError, match="이메일"):
        accounts.create_or_promote_admin(db_session, "   ", name="관리자", password="pw")


# ---------- create_admin: 이미 가입한 이메일이면 승격 ----------

def test_이미_가입한_이메일이면_새로_만들지_않고_승격한다(db_session):
    원래 = 가입시키기(db_session, "user@example.com", name="홍길동", password="원래비밀번호")

    결과, user = accounts.create_or_promote_admin(db_session, "user@example.com")

    assert 결과 == accounts.PROMOTED
    assert user.id == 원래.id           # 같은 계정이어야 한다
    assert user.is_admin is True
    assert 사용자수(db_session) == 1     # 계정이 새로 생기면 안 된다


def test_승격할_때는_이름과_비밀번호를_건드리지_않는다(db_session):
    """실수로 --name 을 줘도 남의 이름·비밀번호가 바뀌면 안 된다."""
    가입시키기(db_session, "user@example.com", name="홍길동", password="원래비밀번호")

    accounts.create_or_promote_admin(
        db_session, "user@example.com", name="엉뚱한이름", password="엉뚱한비밀번호"
    )

    user = accounts.find_user(db_session, "user@example.com")
    assert user.name == "홍길동"
    assert verify_password("원래비밀번호", user.password_hash)
    assert not verify_password("엉뚱한비밀번호", user.password_hash)


def test_이미_관리자면_아무것도_바뀌지_않는다(db_session):
    가입시키기(db_session, "admin@example.com", name="관리자", is_admin=True)
    결과, user = accounts.create_or_promote_admin(db_session, "admin@example.com")
    assert 결과 == accounts.ALREADY_ADMIN
    assert user.is_admin is True
    assert 사용자수(db_session) == 1


# ---------- set_admin: 권한 주기 ----------

def test_가입한_사람에게_관리자_권한을_줄_수_있다(db_session):
    가입시키기(db_session, "user@example.com")
    결과, user = accounts.set_admin(db_session, "user@example.com", make_admin=True)
    assert 결과 == accounts.PROMOTED
    assert user.is_admin is True


def test_set_admin_은_없는_이메일이면_오류(db_session):
    with pytest.raises(accounts.AccountError, match="가입된 적 없는 이메일"):
        accounts.set_admin(db_session, "nobody@example.com", make_admin=True)
    assert 사용자수(db_session) == 0  # 계정을 만들어 주지 않는다


def test_이미_관리자에게_다시_권한을_줘도_바뀌는_것이_없다(db_session):
    가입시키기(db_session, "admin@example.com", is_admin=True)
    결과, _ = accounts.set_admin(db_session, "admin@example.com", make_admin=True)
    assert 결과 == accounts.ALREADY_ADMIN


# ---------- set_admin: 권한 해제 ----------

def test_관리자가_둘이면_한_명은_해제할_수_있다(db_session):
    가입시키기(db_session, "admin1@example.com", name="관리자1", is_admin=True)
    가입시키기(db_session, "admin2@example.com", name="관리자2", is_admin=True)

    결과, user = accounts.set_admin(db_session, "admin2@example.com", make_admin=False)

    assert 결과 == accounts.REVOKED
    assert user.is_admin is False
    assert accounts.count_admins(db_session) == 1


def test_마지막_남은_관리자는_해제할_수_없다(db_session):
    가입시키기(db_session, "admin@example.com", name="유일한관리자", is_admin=True)
    가입시키기(db_session, "user@example.com", name="일반사용자")  # 관리자가 아닌 사람은 세지 않는다

    with pytest.raises(accounts.AccountError, match="마지막 남은 관리자"):
        accounts.set_admin(db_session, "admin@example.com", make_admin=False)

    # 정말로 관리자로 남아 있어야 한다
    assert accounts.find_user(db_session, "admin@example.com").is_admin is True
    assert accounts.count_admins(db_session) == 1


def test_둘_중_하나를_해제한_뒤에는_남은_한_명도_해제할_수_없다(db_session):
    가입시키기(db_session, "admin1@example.com", is_admin=True)
    가입시키기(db_session, "admin2@example.com", is_admin=True)

    accounts.set_admin(db_session, "admin2@example.com", make_admin=False)

    with pytest.raises(accounts.AccountError, match="마지막 남은 관리자"):
        accounts.set_admin(db_session, "admin1@example.com", make_admin=False)


def test_원래_일반_사용자면_해제해도_바뀌는_것이_없다(db_session):
    가입시키기(db_session, "admin@example.com", is_admin=True)
    가입시키기(db_session, "user@example.com")

    결과, user = accounts.set_admin(db_session, "user@example.com", make_admin=False)

    assert 결과 == accounts.ALREADY_NORMAL
    assert user.is_admin is False
    assert accounts.count_admins(db_session) == 1  # 관리자 수는 그대로


def test_관리자_목록을_볼_수_있다(db_session):
    가입시키기(db_session, "admin@example.com", name="관리자", is_admin=True)
    가입시키기(db_session, "user@example.com", name="일반사용자")
    assert [u.email for u in accounts.list_admins(db_session)] == ["admin@example.com"]


# ---------- 웹 화면과 이어지는지 확인 ----------

def 권한바꾸기(email: str, make_admin: bool) -> str:
    """스크립트가 하듯 짧게 세션을 열어 권한만 바꾸고 닫는다.

    (세션을 열어 둔 채로 웹 요청을 보내면 SQLite 가 잠겨서 서로 기다리게 된다)
    """
    with SessionLocal() as db:
        결과, _ = accounts.set_admin(db, email, make_admin=make_admin)
    return 결과


def test_승격하면_관리자_API를_쓸_수_있고_해제하면_막힌다(client):
    """스크립트로 바꾼 권한이 실제 웹 서버에도 곧바로 반영되는지 확인한다."""
    headers = auth_headers(client, email="user@example.com", name="홍길동")
    # 관리자가 되기 전에는 막힌다
    assert client.get("/api/admin/reservations", headers=headers).status_code == 403

    # 다른 관리자를 한 명 먼저 만들어 둔다 (나중에 해제할 수 있게)
    signup(client, email="admin@example.com", name="관리자")
    권한바꾸기("admin@example.com", True)

    권한바꾸기("user@example.com", True)
    # 권한은 로그인 토큰이 아니라 DB를 보고 판단하므로 다시 로그인하지 않아도 된다
    assert client.get("/api/admin/reservations", headers=headers).status_code == 200

    권한바꾸기("user@example.com", False)
    assert client.get("/api/admin/reservations", headers=headers).status_code == 403

    # 새로 로그인해도 마찬가지로 막힌다
    다시로그인 = login_headers(client, "user@example.com")
    assert client.get("/api/admin/reservations", headers=다시로그인).status_code == 403
