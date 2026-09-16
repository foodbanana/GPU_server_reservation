"""비밀번호 재설정 (Phase 4).

비밀번호를 잊은 사람이 있으면 관리자가 서버에서 이 스크립트로 바꿔 준다.
(이 시스템에는 이메일로 비밀번호를 찾는 기능이 없다 — SPEC 범위 밖)

쓰는 법 (backend 폴더에서):
    PYTHONPATH= venv/bin/python scripts/reset_password.py someone@example.com
    PYTHONPATH= venv/bin/python scripts/reset_password.py          # 이메일도 물어본다

- 새 비밀번호는 화면에 보이지 않게 두 번 입력받아 bcrypt 해시로 바꿔 저장한다.
- 없는 이메일이면 오류를 내고 아무것도 바꾸지 않는다.
- 관리자 본인 계정도 똑같이 재설정할 수 있다.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))


def 비밀번호입력(password_too_long) -> str:
    """새 비밀번호를 두 번 받아서 확인한다. 입력은 화면에 보이지 않는다."""
    while True:
        try:
            pw = getpass.getpass("새 비밀번호 (입력해도 화면에 보이지 않습니다): ")
            확인 = getpass.getpass("새 비밀번호 확인: ")
        except (EOFError, KeyboardInterrupt):
            print()
            raise SystemExit(1)

        if not pw:
            print("  비밀번호를 입력해 주세요.")
        elif password_too_long(pw):
            print("  비밀번호가 너무 깁니다. 더 짧게 입력해 주세요.")
        elif pw != 확인:
            print("  두 번 입력한 비밀번호가 서로 다릅니다. 다시 입력해 주세요.")
        else:
            return pw


def main() -> None:
    parser = argparse.ArgumentParser(description="사용자 한 명의 비밀번호를 새로 정한다.")
    parser.add_argument("email", nargs="?", help="비밀번호를 바꿀 사용자의 이메일")
    args = parser.parse_args()

    try:
        from sqlalchemy import select

        from app.database import SessionLocal
        from app.models import User
        from app.security import hash_password, password_too_long
    except RuntimeError as exc:  # 설정 파일이 없거나 값이 비었을 때
        print(f"오류: {exc}", file=sys.stderr)
        raise SystemExit(1)

    email = args.email
    if not email:
        try:
            email = input("이메일: ")
        except (EOFError, KeyboardInterrupt):
            print()
            raise SystemExit(1)
    email = email.strip().lower()

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            print(f"오류: 가입된 적 없는 이메일입니다: {email}", file=sys.stderr)
            print("(가입할 때 쓴 이메일을 정확히 입력했는지 확인해 주세요)", file=sys.stderr)
            raise SystemExit(1)

        print(f"대상: {user.name} ({user.email})")
        password = 비밀번호입력(password_too_long)
        user.password_hash = hash_password(password)
        db.commit()
        이름 = user.name

    print(f"완료: {이름} 님의 비밀번호를 바꿨습니다. 새 비밀번호로 로그인하면 됩니다.")


if __name__ == "__main__":
    main()
