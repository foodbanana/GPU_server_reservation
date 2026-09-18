"""Vercel 서버리스 함수 진입점.

Vercel 은 저장소 루트의 `api/` 폴더에 있는 파이썬 파일을 '서버리스 함수'로 만든다.
그리고 그 파일 안의 `app` 변수를 찾아서 FastAPI 앱으로 인식한다.
이 파일이 하는 일은 딱 세 가지다.

  1) backend/ 안의 `app` 패키지를 import 할 수 있게 경로를 잡아 준다
     (서버리스에서 'ModuleNotFoundError: No module named app' 이 나는 가장 흔한 원인)
  2) 설정 파일을 backend/config.vercel.yaml 로 지정한다 (비밀값은 환경변수로 들어온다)
  3) 콜드스타트마다 DB 초기화가 돌지 않도록 끈다 (app/db_init.py 참고)

화면(Vue)은 Vercel 이 직접 내보내므로 이 함수는 API만 담당한다.
config.vercel.yaml 의 static_dir 가 비어 있어서 FastAPI 는 정적 파일을 서빙하지 않는다.

로컬 개발과 직접 운영(systemd)은 이 파일을 전혀 쓰지 않는다. 그쪽은 그대로다.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _find_backend_dir() -> Path:
    """backend 폴더를 찾는다.

    보통은 이 파일(api/index.py)의 한 단계 위가 저장소 루트고 그 안에 backend/ 가 있다.
    서버리스 환경에서 파일이 다른 위치에 놓이더라도 동작하도록 위로 올라가며 찾는다.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "backend"
        if (candidate / "app" / "main.py").is_file():
            return candidate
    찾아본곳 = ", ".join(str(p / "backend") for p in list(here.parents)[:4])
    raise RuntimeError(
        "backend 폴더를 찾지 못했습니다. vercel.json 의 includeFiles 에 "
        f"backend/** 가 들어 있는지 확인해 주세요. (찾아본 곳: {찾아본곳})"
    )


BACKEND_DIR = _find_backend_dir()

# 1) backend 를 import 경로에 넣는다 -> `from app.main import app` 이 동작한다
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# 2) 설정 파일 지정. 대시보드에서 GPU_RESERVE_CONFIG 를 따로 넣었다면 그걸 존중한다.
os.environ.setdefault("GPU_RESERVE_CONFIG", str(BACKEND_DIR / "config.vercel.yaml"))

# 3) 콜드스타트마다 테이블 생성·GPU 등록이 돌면 느리다. 여기서는 끈다.
#    (배포 전에 `scripts/init_db.py` 를 한 번 실행해 두어야 한다)
os.environ.setdefault("GPU_RESERVE_SKIP_DB_INIT", "1")

# DB 주소가 없으면 여기서 분명하게 알려 준다.
# Vercel 은 파일을 저장할 수 없어 SQLite 를 쓸 수 없고, 그대로 두면
# "테이블이 없습니다" 같은 알아보기 힘든 오류로 번진다.
if not os.environ.get("DATABASE_URL", "").strip():
    raise RuntimeError(
        "DATABASE_URL 환경변수가 없습니다. "
        "Vercel 대시보드 Settings > Environment Variables 에 Neon Postgres 주소를 "
        "DATABASE_URL 이라는 이름으로 넣어 주세요."
    )

from app.main import app  # noqa: E402  (위에서 경로·환경변수를 맞춘 뒤여야 한다)

__all__ = ["app"]
