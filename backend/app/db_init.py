"""DB 첫 준비 — 테이블 만들기 + 겹침 금지 제약 + GPU 12장 등록.

세 가지를 한 번에 한다. 모두 **여러 번 실행해도 안전하다**(멱등).
  1) 없는 테이블만 만든다
  2) Postgres 면 겹침 금지 제약을 건다 (이미 있으면 그냥 넘어간다)
  3) config 의 gpus 목록대로 GPU 를 추가·갱신한다

--------------------------------------------------
언제 실행되나 — 직접 운영 vs Vercel(서버리스)
--------------------------------------------------
* 직접 운영(systemd, 로컬 개발): 지금까지처럼 **서버를 켤 때 자동으로** 실행된다.
  서버가 한 번 켜지면 계속 떠 있으므로 시작할 때 한 번만 도는 셈이다.

* Vercel(서버리스): 요청이 뜸하면 함수가 잠들고, 다시 요청이 오면 새로 깨어난다
  (이걸 '콜드스타트'라고 한다). 그때마다 위 1~3번을 다 돌리면 DB에 쓸데없는
  왕복이 수십 번 생겨 느려진다. 그래서 **Vercel 에서는 자동 실행을 끄고**,
  사용자가 아래 명령으로 딱 한 번 직접 실행한다.

      cd backend
      DATABASE_URL='...' GPU_RESERVE_CONFIG=config.vercel.yaml \
        PYTHONPATH= venv/bin/python scripts/init_db.py

  (GPU 목록을 바꿨을 때도 이 명령을 다시 실행하면 된다)

Vercel 인지 아닌지는 Vercel 이 자동으로 넣어 주는 `VERCEL` 환경변수로 알아낸다.
환경변수 GPU_RESERVE_SKIP_DB_INIT 로 직접 켜고 끌 수도 있다.
"""

from __future__ import annotations

import os

from app.database import Base, SessionLocal, engine
from app.models import ensure_overlap_constraint  # noqa: F401  (테이블 등록도 겸한다)
from app.seed import seed_gpus

#: "1"/"true" 면 서버를 켤 때 초기화를 건너뛴다. "0"/"false" 면 반드시 한다.
ENV_SKIP_DB_INIT = "GPU_RESERVE_SKIP_DB_INIT"

_참_거짓 = {"1": True, "true": True, "yes": True, "on": True,
            "0": False, "false": False, "no": False, "off": False}

# 한 프로세스 안에서 두 번 돌지 않게 하는 표시
_initialized = False


def initialize_database(*, force: bool = False) -> None:
    """테이블·제약·GPU 를 준비한다. 이미 했으면 다시 하지 않는다.

    force=True 면 표시를 무시하고 다시 실행한다 (scripts/init_db.py 에서 사용).
    """
    global _initialized
    if _initialized and not force:
        return

    Base.metadata.create_all(bind=engine)
    # Postgres 면 '시간 겹침 금지' 제약을 건다 (SQLite 면 아무 일도 안 한다).
    ensure_overlap_constraint(engine)
    with SessionLocal() as db:
        seed_gpus(db)

    _initialized = True


def should_init_on_startup() -> bool:
    """서버를 켤 때 initialize_database() 를 자동으로 돌려야 하는가."""
    flag = os.environ.get(ENV_SKIP_DB_INIT, "").strip().lower()
    if flag in _참_거짓:
        return not _참_거짓[flag]
    # 따로 정하지 않았으면: Vercel 에서는 건너뛰고, 그 외(직접 운영·로컬)에서는 한다.
    return not os.environ.get("VERCEL")
