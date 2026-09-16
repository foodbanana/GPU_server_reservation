"""관리자 권한 주기 / 뺏기 (Phase 4).

이미 가입한 사람에게 관리자 권한을 주거나 다시 뺏는다.

쓰는 법 (backend 폴더에서):
    PYTHONPATH= venv/bin/python scripts/set_admin.py someone@example.com            # 권한 주기
    PYTHONPATH= venv/bin/python scripts/set_admin.py someone@example.com --revoke   # 권한 뺏기
    PYTHONPATH= venv/bin/python scripts/set_admin.py --list                         # 지금 관리자 목록

- 가입한 적 없는 이메일이면 오류를 내고 아무것도 바꾸지 않는다.
  (계정까지 새로 만들려면 scripts/create_admin.py 를 쓴다)
- **마지막 남은 관리자의 권한은 해제할 수 없다.** 아무도 관리자 화면에 못 들어가게 되기 때문이다.
  다른 사람을 먼저 관리자로 지정한 뒤에 해제해야 한다.

실제 판단은 app/services/accounts.py 가 한다 (테스트도 그 파일을 확인한다).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))


def main() -> None:
    parser = argparse.ArgumentParser(description="이메일로 관리자 권한을 주거나 뺏는다.")
    parser.add_argument("email", nargs="?", help="권한을 바꿀 사용자의 이메일")
    parser.add_argument(
        "--revoke", action="store_true", help="권한을 주는 대신 뺏는다"
    )
    parser.add_argument(
        "--list", action="store_true", dest="show_list", help="지금 관리자 목록만 보여주고 끝낸다"
    )
    args = parser.parse_args()

    try:
        from app.database import SessionLocal
        from app.services import accounts
    except RuntimeError as exc:  # 설정 파일이 없거나 값이 비었을 때
        print(f"오류: {exc}", file=sys.stderr)
        raise SystemExit(1)

    with SessionLocal() as db:
        if args.show_list:
            관리자목록출력(db, accounts)
            return

        email = args.email
        if not email:
            try:
                email = input("이메일: ")
            except (EOFError, KeyboardInterrupt):
                print()
                raise SystemExit(1)

        try:
            결과, user = accounts.set_admin(db, email, make_admin=not args.revoke)
        except accounts.AccountError as exc:
            print(f"오류: {exc}", file=sys.stderr)
            raise SystemExit(1)

        이름, 이메일 = user.name, user.email

        if 결과 == accounts.PROMOTED:
            print(f"완료: {이름}({이메일}) 님이 이제 관리자입니다.")
            print("(이미 로그인 중이라면 로그아웃했다가 다시 로그인해야 관리자 메뉴가 보입니다)")
        elif 결과 == accounts.REVOKED:
            print(f"완료: {이름}({이메일}) 님의 관리자 권한을 해제했습니다.")
            print("(그 사람 화면에서 관리자 메뉴가 사라지고, 주소를 직접 입력해도 서버가 막습니다)")
        elif 결과 == accounts.ALREADY_ADMIN:
            print(f"{이름}({이메일}) 님은 이미 관리자입니다. 바뀐 것은 없습니다.")
        else:  # ALREADY_NORMAL
            print(f"{이름}({이메일}) 님은 원래 관리자가 아닙니다. 바뀐 것은 없습니다.")

        print()
        관리자목록출력(db, accounts)


def 관리자목록출력(db, accounts) -> None:
    관리자들 = accounts.list_admins(db)
    if not 관리자들:
        print("지금 관리자가 한 명도 없습니다. scripts/create_admin.py 로 만들어 주세요.")
        return
    print(f"현재 관리자 {len(관리자들)}명:")
    for u in 관리자들:
        print(f"  - {u.name} ({u.email})")


if __name__ == "__main__":
    main()
