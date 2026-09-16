"""비밀번호 해시(bcrypt)와 로그인 토큰(JWT) 처리."""

from __future__ import annotations

from datetime import timedelta

import bcrypt
import jwt

from app import timeutil
from app.config import get_config

ALGORITHM = "HS256"
# bcrypt 는 72바이트까지만 처리한다. 그보다 길면 조용히 잘리므로 미리 막는다.
MAX_PASSWORD_BYTES = 72


def password_too_long(password: str) -> bool:
    return len(password.encode("utf-8")) > MAX_PASSWORD_BYTES


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # 해시 형식이 깨진 경우
        return False


def create_access_token(user_id: int) -> str:
    """로그인 성공 시 발급하는 '출입증' 문자열. 기본 30일짜리."""
    config = get_config()
    now = timeutil.now_kst().replace(tzinfo=timeutil.KST)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=config.jwt_expire_days)).timestamp()),
    }
    return jwt.encode(payload, config.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> int | None:
    """토큰이 올바르면 사용자 id, 아니면 None.

    만료 검사는 PyJWT에 맡기지 않고 직접 한다.
    앱 전체가 '지금 몇 시인가'를 timeutil.now_kst() 한 곳에서만 보게 하기 위해서다.
    """
    try:
        payload = jwt.decode(
            token,
            get_config().jwt_secret,
            algorithms=[ALGORITHM],
            options={"verify_exp": False},
        )
        now_ts = timeutil.now_kst().replace(tzinfo=timeutil.KST).timestamp()
        if now_ts >= int(payload["exp"]):
            return None
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        return None
