"""회원가입 가입 코드 검사와 로그인 테스트 (SPEC 6장)."""

from __future__ import annotations

from tests.conftest import TEST_INVITE_CODE, auth_headers, signup


def test_가입코드가_맞으면_가입된다(client):
    user = signup(client, email="ok@example.com", name="김철수")
    assert user["email"] == "ok@example.com"
    assert user["name"] == "김철수"
    assert user["is_admin"] is False
    # 응답에 비밀번호 관련 정보가 들어 있으면 안 된다
    assert "password" not in user and "password_hash" not in user


def test_가입코드가_틀리면_가입되지_않는다(client):
    response = client.post(
        "/api/auth/signup",
        json={
            "name": "김철수",
            "email": "bad@example.com",
            "password": "test-pw-1234",
            "invite_code": "WRONG-CODE",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "연구실 가입 코드가 올바르지 않습니다."

    # 가입되지 않았으므로 로그인도 안 된다
    login = client.post(
        "/api/auth/login",
        json={"email": "bad@example.com", "password": "test-pw-1234"},
    )
    assert login.status_code == 401


def test_가입코드가_비어있으면_가입되지_않는다(client):
    response = client.post(
        "/api/auth/signup",
        json={
            "name": "김철수",
            "email": "empty@example.com",
            "password": "test-pw-1234",
            "invite_code": "",
        },
    )
    assert response.status_code == 400


def test_같은_이메일로_두_번_가입할_수_없다(client):
    signup(client, email="dup@example.com")
    response = client.post(
        "/api/auth/signup",
        json={
            "name": "다른사람",
            "email": "dup@example.com",
            "password": "test-pw-1234",
            "invite_code": TEST_INVITE_CODE,
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "이미 가입된 이메일입니다."


def test_비밀번호는_한_글자여도_가입된다(client):
    """비밀번호 최소 글자 수 제한은 두지 않는다."""
    response = client.post(
        "/api/auth/signup",
        json={
            "name": "김철수",
            "email": "short-pw@example.com",
            "password": "a",
            "invite_code": TEST_INVITE_CODE,
        },
    )
    assert response.status_code == 201, response.text

    # 그 비밀번호로 로그인도 되어야 한다
    login = client.post(
        "/api/auth/login", json={"email": "short-pw@example.com", "password": "a"}
    )
    assert login.status_code == 200, login.text


def test_빈_비밀번호는_거부된다(client):
    response = client.post(
        "/api/auth/signup",
        json={
            "name": "김철수",
            "email": "empty-pw@example.com",
            "password": "",
            "invite_code": TEST_INVITE_CODE,
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "비밀번호를 입력해 주세요."


def test_너무_긴_비밀번호는_거부된다(client):
    """bcrypt 는 72바이트까지만 처리하므로 조용히 잘리지 않게 막는다."""
    response = client.post(
        "/api/auth/signup",
        json={
            "name": "김철수",
            "email": "long-pw@example.com",
            "password": "가" * 30,  # 한글 1자 = 3바이트 -> 90바이트
            "invite_code": TEST_INVITE_CODE,
        },
    )
    assert response.status_code == 400
    assert "너무 깁니다" in response.json()["detail"]


def test_비밀번호가_틀리면_로그인_실패(client):
    signup(client, email="pw@example.com")
    response = client.post(
        "/api/auth/login", json={"email": "pw@example.com", "password": "wrong-pw-1234"}
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "이메일 또는 비밀번호가 올바르지 않습니다."


def test_비밀번호는_해시로_저장된다(client, db_session):
    from sqlalchemy import select

    from app.models import User

    signup(client, email="hash@example.com", password="test-pw-1234")
    user = db_session.scalar(select(User).where(User.email == "hash@example.com"))
    db_session.rollback()  # 읽기 트랜잭션을 닫아 준다
    assert user.password_hash != "test-pw-1234"
    assert user.password_hash.startswith("$2")  # bcrypt 해시 형식


def test_로그인하면_내_정보를_볼_수_있다(client):
    headers = auth_headers(client, email="me@example.com", name="이영희")
    response = client.get("/api/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == "이영희"


def test_토큰이_없으면_401(client):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/gpus").status_code == 401


def test_엉터리_토큰이면_401(client):
    response = client.get(
        "/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401


def test_만료된_토큰이면_401(client, clock):
    from datetime import timedelta

    headers = auth_headers(client, email="expire@example.com")
    assert client.get("/api/auth/me", headers=headers).status_code == 200

    # 토큰 유효기간(30일)이 지난 뒤로 시계를 돌린다
    clock.set(clock.now + timedelta(days=31))
    assert client.get("/api/auth/me", headers=headers).status_code == 401
