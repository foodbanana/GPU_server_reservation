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

import os

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


# ---------------------------------------------------------------------------
# 웹 화면에서 관리자 권한 바꾸기 (관리자 화면의 '가입자' 탭)
# ---------------------------------------------------------------------------
# 위의 set_admin() 은 터미널 스크립트(scripts/set_admin.py)가 쓰는 함수다.
# 웹에서는 규칙이 두 가지 더 필요하다.
#
#   1) 슈퍼 관리자 보호 — 정해 둔 이메일 한 개는 누구도(본인 포함) 해제할 수 없다.
#      이 이메일은 코드에 적지 않고 환경변수로 받는다. 환경변수가 없으면
#      '보호할 대상이 없는' 것으로 보고 이 보호만 꺼진다. (나머지 기능은 그대로 동작)
#
#   2) 본인 해제 금지 — 관리자가 자기 권한을 스스로 빼면 그 순간 관리자 화면에서
#      튕겨 나가 혼란스럽다. 다른 관리자에게 부탁하도록 막는다.
#
# '마지막 남은 관리자는 해제할 수 없다'는 규칙은 set_admin() 이 이미 하고 있으므로
# 그대로 재사용한다. 터미널과 웹이 같은 규칙을 쓰게 하기 위해서다.

#: 슈퍼 관리자 이메일을 담는 환경변수 이름 (값은 Vercel 대시보드 등에서 넣는다)
ENV_SUPER_ADMIN_EMAIL = "GPU_RESERVE_SUPER_ADMIN_EMAIL"


def super_admin_email() -> str | None:
    """보호할 슈퍼 관리자 이메일. 환경변수가 없거나 비어 있으면 None.

    호출할 때마다 환경변수를 읽는다(불러올 때 한 번만 읽지 않는다).
    그래야 테스트에서 값을 바꿔 가며 확인할 수 있다.
    """
    value = os.environ.get(ENV_SUPER_ADMIN_EMAIL, "").strip().lower()
    return value or None


def is_super_admin_email(email: str | None) -> bool:
    """이 이메일이 보호 대상(슈퍼 관리자)인가. 환경변수가 없으면 항상 False."""
    보호대상 = super_admin_email()
    if 보호대상 is None:
        return False
    return (email or "").strip().lower() == 보호대상


def change_admin_status(
    db: Session,
    *,
    target: User,
    make_admin: bool,
    actor: User | None = None,
) -> tuple[str, User]:
    """웹 화면에서 관리자 권한을 주거나 뺏는다.

    target: 권한을 바꿀 사람 (라우터가 id 나 이메일로 이미 찾아 둔 사용자)
    actor:  이 작업을 하는 관리자 (본인 해제를 막는 데 쓴다)

    규칙을 어기면 AccountError 를 던진다. 돌려주는 값은 set_admin() 과 같다.
    """
    if not make_admin:
        # 1) 슈퍼 관리자는 누구도 해제할 수 없다 (본인도 마찬가지)
        if is_super_admin_email(target.email):
            raise AccountError(
                f"{target.name}({target.email}) 님은 이 서비스의 최고 관리자입니다. "
                "관리자 권한을 해제할 수 없습니다."
            )

        # 2) 자기 자신은 해제할 수 없다
        if actor is not None and actor.id == target.id:
            raise AccountError(
                "자기 자신의 관리자 권한은 해제할 수 없습니다. "
                "다른 관리자에게 부탁해 주세요."
            )

    # 3) 나머지 규칙(마지막 관리자 보호, 이미 관리자/일반인 경우)은 터미널과 동일하다
    return set_admin(db, target.email, make_admin=make_admin)
