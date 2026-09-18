"""DB 첫 준비 — 테이블 · 겹침 금지 제약 · GPU 12장을 만든다.

**Vercel 에 배포할 때 딱 한 번 실행하는 명령이다.**
Vercel(서버리스)에서는 서버가 켜질 때마다 이 작업을 하면 느려지므로 자동 실행을 껐다.
그래서 사람이 한 번 직접 실행해 준다. (자세한 이유는 app/db_init.py 참고)

쓰는 법 (backend 폴더에서):

    # Neon Postgres 를 준비할 때 (Vercel 배포 전에 한 번)
    DATABASE_URL='postgresql://...neon.tech/DB이름?sslmode=require' \
    GPU_RESERVE_CONFIG=config.vercel.yaml \
    GPU_RESERVE_INVITE_CODE='가입코드' GPU_RESERVE_JWT_SECRET='비밀키' \
      PYTHONPATH= venv/bin/python scripts/init_db.py

    # 지금 설정 파일 기준으로 그냥 준비만 (SQLite 도 됨)
    PYTHONPATH= venv/bin/python scripts/init_db.py

여러 번 실행해도 안전하다. 이미 있는 테이블·제약·GPU 는 건드리지 않는다.
**기존 예약이나 계정은 절대 지우지 않는다.**
config.yaml 의 gpus 목록을 바꿨을 때 다시 실행하면 GPU 목록만 갱신된다.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))


def main() -> None:
    try:
        from app.config import get_config
        from app.database import IS_POSTGRES, engine
        from app.db_init import initialize_database
        from app.models import Gpu
    except RuntimeError as exc:  # 설정 파일·비밀값 문제
        print(f"설정을 읽지 못했습니다:\n{exc}")
        raise SystemExit(1)

    config = get_config()

    if IS_POSTGRES:
        # 비밀번호가 화면에 찍히지 않도록 주소는 보여 주지 않는다
        어디에 = f"Postgres ({engine.url.host or '로컬 소켓'} / {engine.url.database})"
    else:
        어디에 = f"SQLite ({config.database_path})"
    print(f"준비할 DB: {어디에}")

    initialize_database(force=True)

    from sqlalchemy import func, select

    from app.database import SessionLocal

    with SessionLocal() as db:
        gpu_수 = db.scalar(select(func.count(Gpu.id)))

    print("끝났습니다.")
    print(f"  - 테이블 준비 완료")
    print(f"  - 겹침 금지 제약: {'걸었습니다' if IS_POSTGRES else '해당 없음 (SQLite 는 잠금으로 처리)'}")
    print(f"  - 등록된 GPU: {gpu_수}장")
    print()
    print("다음 순서: 관리자 계정을 만드세요.")
    print("  PYTHONPATH= venv/bin/python scripts/create_admin.py")


if __name__ == "__main__":
    main()
