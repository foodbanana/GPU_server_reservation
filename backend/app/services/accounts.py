"""계정 관리 — 관리자 계정 만들기, 관리자 권한 부여·해제.

명령줄 스크립트(scripts/create_admin.py, scripts/set_admin.py)가 쓰는 실제 로직이다.
스크립트 파일 안에 로직을 두면 pytest 로 확인하기 어려워서 여기로 모았다.
스크립트는 '물어보고 출력하는 일'만 하고, 판단은 전부 이 파일이 한다.

규칙:
- 이미 가입한 이메일이면 계정을 새로 만들지 않고 그 계정을 관리자로 승격한다.
  (비밀번호는 그대로 둔다 — 남의 비밀번호를 말없이 바꾸면 안 되므로)
- 마지막 남은 관리자의 권한은 해제할 수 없다. (아무도 관리자 화면에 못 들어가게 되는 것을 막는다)
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import User
from app.security import hash_password, password_too_long

# 결과 코드 — 스크립트와 테스트가 '무슨 일이 일어났는지' 구분하는 데 쓴다
CREATED = "created"            # 관리자 계정을 새로 만들었다
PROMOTED = "promoted"          # 있던 계정을 관리자로 올렸다
ALREADY_ADMIN = "already_admin"  # 이미 관리자라 바뀐 것이 없다
REVOKED = "revoked"            # 관리자 권한을 뺏었다
ALREADY_NORMAL = "already_normal"  # 원래 일반 사용자라 바뀐 것이 없다


class AccountError(Exception):
    """사람이 읽을 수 있는 한국어 메시지를 담은 오류."""


def normalize_email(email: str | None) -> str:
    email = (email or "").strip().lower()
    if not email:
        raise AccountError("이메일을 입력해 주세요.")
    return email


def find_user(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == normalize_email(email)))


def count_admins(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(User).where(User.is_admin.is_(True))) or 0


def list_admins(db: Session) -> list[User]:
    return list(db.scalars(select(User).where(User.is_admin.is_(True)).order_by(User.id)).all())


def _check_password(password: str | None) -> str:
    if not password:
        raise AccountError("비밀번호를 입력해 주세요.")
    if password_too_long(password):
        raise AccountError("비밀번호가 너무 깁니다. 더 짧게 입력해 주세요.")
    return password


def create_or_promote_admin(
    db: Session,
    email: str,
    *,
    name: str | None = None,
    password: str | None = None,
) -> tuple[str, User]:
    """관리자 계정을 준비한다.

    - 이미 가입한 이메일이면: **새로 만들지 않고** 그 계정을 관리자로 승격한다.
      이때 name·password 는 무시한다 (기존 계정의 이름·비밀번호를 건드리지 않는다).
    - 없는 이메일이면: name 과 password 를 받아 관리자 계정을 새로 만든다.

    돌려주는 값: (결과 코드, 사용자)
    """
    email = normalize_email(email)
    user = find_user(db, email)

    if user is not None:
        if user.is_admin:
            return ALREADY_ADMIN, user
        user.is_admin = True
        db.commit()
        db.refresh(user)
        return PROMOTED, user

    name = (name or "").strip()
    if not name:
        raise AccountError("새 계정을 만들려면 이름이 필요합니다.")
    password = _check_password(password)

    user = User(
        name=name,
        email=email,
        password_hash=hash_password(password),
        is_admin=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return CREATED, user


def set_admin(db: Session, email: str, *, make_admin: bool) -> tuple[str, User]:
    """이미 가입한 계정의 관리자 권한을 주거나 뺏는다.

    마지막 남은 관리자는 해제할 수 없다.
    돌려주는 값: (결과 코드, 사용자)
    """
    email = normalize_email(email)
    user = find_user(db, email)
    if user is None:
        raise AccountError(
            f"가입된 적 없는 이메일입니다: {email}\n"
            "먼저 웹에서 회원가입을 하거나, scripts/create_admin.py 로 계정을 만들어 주세요."
        )

    if make_admin:
        if user.is_admin:
            return ALREADY_ADMIN, user
        user.is_admin = True
        db.commit()
        db.refresh(user)
        return PROMOTED, user

    if not user.is_admin:
        return ALREADY_NORMAL, user

    if count_admins(db) <= 1:
        raise AccountError(
            f"{user.name}({user.email}) 님은 마지막 남은 관리자입니다.\n"
            "권한을 해제하면 아무도 관리자 화면에 들어갈 수 없게 되므로 막았습니다.\n"
            "다른 사람을 먼저 관리자로 지정한 뒤에 다시 해제해 주세요."
        )

    user.is_admin = False
    db.commit()
    db.refresh(user)
    return REVOKED, user
