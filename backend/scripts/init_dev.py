"""개발용 설정과 개발용 DB 준비하기 (Phase 5).

왜 필요한가:
  운영 서버(포트 9080)는 systemd 가 계속 켜 두고, 진짜 DB(`data/gpu.db`)를 쓴다.
  앞으로 코드를 고칠 때 그 서버와 그 DB를 건드리면 안 된다.
  그래서 **개발 전용 설정 파일과 개발 전용 DB**를 따로 만들어 두고,
  개발할 때는 포트 9081 + 개발용 DB 로만 서버를 켠다.

만드는 것:
  backend/config.dev.yaml   개발용 설정 (가입 코드·비밀키가 운영과 다르다)
  backend/dev/dev.db        개발용 DB (서버를 처음 켤 때 자동 생성)

쓰는 법 (backend 폴더에서):
    PYTHONPATH= venv/bin/python scripts/init_dev.py

두 파일 모두 .gitignore 에 들어 있어 git 에 올라가지 않는다.
개발 데이터를 싹 비우고 싶으면 `rm -f dev/dev.db*` 만 하면 된다.
(운영 DB `data/gpu.db` 는 이 스크립트가 절대 읽지도 쓰지도 않는다)
"""

from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

import yaml

BACKEND_DIR = Path(__file__).resolve().parent.parent

DEV_CONFIG_PATH = BACKEND_DIR / "config.dev.yaml"
DEV_DIR = BACKEND_DIR / "dev"
DEV_DB_PATH = DEV_DIR / "dev.db"
DEV_INVITE_CODE = "DEV-CODE-1234"

머리말 = """\
# 개발 전용 설정. scripts/init_dev.py 가 만든다. git 에 올라가지 않는다.
#
# 운영 설정(config.yaml)과 다른 점:
#   - DB 가 dev/dev.db  (운영 DB data/gpu.db 는 절대 쓰지 않는다)
#   - 화면(static_dir)을 서빙하지 않는다. 개발 중에는 vite(5173)가 화면을 맡는다.
#   - 가입 코드와 JWT 비밀키가 운영과 다르다.
#
# 이 설정으로 서버 켜기 (backend 폴더에서, 포트 9081):
#   GPU_RESERVE_CONFIG=config.dev.yaml PYTHONPATH= \\
#     venv/bin/python -m uvicorn app.main:app --reload --port 9081
"""


def 원본설정() -> dict:
    """GPU 목록과 규칙은 실제 설정에서 가져온다 (없으면 예시 파일)."""
    for name in ("config.yaml", "config.example.yaml"):
        path = BACKEND_DIR / name
        if path.exists():
            return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raise SystemExit(
        "config.yaml 도 config.example.yaml 도 없습니다. backend 폴더에서 실행해 주세요."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="개발용 설정(config.dev.yaml) 만들기")
    parser.add_argument(
        "--force",
        action="store_true",
        help="config.dev.yaml 이 이미 있어도 새로 만든다 (비밀키가 바뀌어 다시 로그인해야 함)",
    )
    args = parser.parse_args()

    if DEV_CONFIG_PATH.exists() and not args.force:
        print(f"이미 있습니다: {DEV_CONFIG_PATH}")
        print("그대로 쓰면 됩니다. 새로 만들려면 --force 를 붙이세요.")
        return 0

    raw = 원본설정()
    raw.setdefault("app", {})
    raw["app"]["invite_code"] = DEV_INVITE_CODE
    raw["app"]["jwt_secret"] = secrets.token_urlsafe(48)
    # 운영 DB 와 섞이지 않도록 개발용 경로로 덮어쓴다.
    raw["app"]["database_path"] = "dev/dev.db"
    # 개발 중 화면은 vite 가 맡으므로 빌드 결과는 서빙하지 않는다.
    raw["app"]["static_dir"] = ""
    raw.setdefault("google", {})
    raw["google"]["enabled"] = False

    DEV_DIR.mkdir(parents=True, exist_ok=True)
    DEV_CONFIG_PATH.write_text(
        머리말 + "\n" + yaml.safe_dump(raw, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    print("개발용 설정을 만들었습니다. (운영 DB data/gpu.db 는 건드리지 않았습니다)")
    print(f"  설정 파일 : {DEV_CONFIG_PATH}")
    print(f"  개발용 DB : {DEV_DB_PATH}  (서버를 처음 켤 때 자동으로 생깁니다)")
    print(f"  가입 코드 : {DEV_INVITE_CODE}")
    print()
    print("개발 서버 켜기 — 터미널 2개:")
    print("  [1] cd backend && GPU_RESERVE_CONFIG=config.dev.yaml PYTHONPATH= \\")
    print("        venv/bin/python -m uvicorn app.main:app --reload --port 9081")
    print("  [2] cd frontend && npm run dev     ->  http://localhost:5173")
    return 0


if __name__ == "__main__":
    sys.exit(main())
