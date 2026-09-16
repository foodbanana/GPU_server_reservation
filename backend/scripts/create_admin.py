"""관리자 계정 만들기 (Phase 4).

관리자 화면(전체 예약 수정·삭제)은 관리자 계정으로만 들어갈 수 있는데,
웹 회원가입으로는 관리자가 될 수 없다. 그래서 이 스크립트로 직접 만든다.

쓰는 법 (backend 폴더에서):
    PYTHONPATH= venv/bin/python scripts/create_admin.py
    PYTHONPATH= venv/bin/python scripts/create_admin.py --email me@example.com --name 홍길동

- **이미 가입한 이메일이면 계정을 새로 만들지 않고 그 계정을 관리자로 올린다.**
  (이름과 비밀번호는 그대로 둔다. 비밀번호를 바꾸려면 scripts/reset_password.py 를 쓴다)
- 없는 이메일이면 이름과 비밀번호를 물어보고 관리자 계정을 새로 만든다.
  비밀번호는 입력해도 화면에 보이지 않는다.
- 설정 파일(config.yaml)에 적힌 DB를 그대로 쓴다.

실제 판단은 app/services/accounts.py 가 한다 (테스트도 그 파일을 확인한다).
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))


def 물어보기(문구: str) -> str:
    try:
        return input(문구).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raise SystemExit(1)


def 비밀번호입력(password_too_long) -> str:
    """새 비밀번호를 두 번 받아서 확인한다. 입력은 화면에 보이지 않는다."""
    while True:
        try:
            pw = getpass.getpass("비밀번호 (입력해도 화면에 보이지 않습니다): ")
            확인 = getpass.getpass("비밀번호 확인: ")
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
    parser = argparse.ArgumentParser(
        description="관리자 계정을 만든다. 이미 가입한 이메일이면 그 계정을 관리자로 올린다."
    )
    parser.add_argument("--email", help="관리자로 쓸 이메일 (없으면 물어본다)")
    parser.add_argument("--name", help="이름 (계정을 새로 만들 때만 씀)")
    args = parser.parse_args()

    # app 모듈은 import 하는 순간 config.yaml 을 읽는다. 설정이 없으면 친절히 알려준다.
    try:
        from app.database import Base, SessionLocal, engine
        from app.security import password_too_long
        from app.services import accounts
    except RuntimeError as exc:  # 설정 파일이 없거나 값이 비었을 때
        print(f"오류: {exc}", file=sys.stderr)
        raise SystemExit(1)

    # DB 파일이 아직 없으면(서버를 한 번도 켜지 않은 경우) 테이블만 만들어 준다.
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        try:
            email = accounts.normalize_email(args.email or 물어보기("이메일: "))
            기존 = accounts.find_user(db, email)

            name = None
            password = None
            if 기존 is None:
                # 새 계정을 만들 때만 이름·비밀번호를 물어본다
                name = args.name or 물어보기("이름: ")
                password = 비밀번호입력(password_too_long)

            결과, user = accounts.create_or_promote_admin(
                db, email, name=name, password=password
            )
        except accounts.AccountError as exc:
            print(f"오류: {exc}", file=sys.stderr)
            raise SystemExit(1)

        이름, 이메일 = user.name, user.email

    if 결과 == accounts.CREATED:
        print(f"완료: 관리자 계정을 만들었습니다. ({이름} / {이메일})")
        print("이제 웹 화면에서 이 이메일과 비밀번호로 로그인하면 '관리자' 메뉴가 보입니다.")
    elif 결과 == accounts.PROMOTED:
        print(f"완료: 이미 가입된 계정이라 새로 만들지 않고 관리자로 올렸습니다. ({이름} / {이메일})")
        print("(이미 로그인 중이라면 로그아웃했다가 다시 로그인해야 관리자 메뉴가 보입니다)")
    else:  # ALREADY_ADMIN
        print(f"{이름}({이메일}) 님은 이미 관리자입니다. 바뀐 것은 없습니다.")


if __name__ == "__main__":
    main()
