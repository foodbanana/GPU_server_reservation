"""타임라인 화면 확인용 '가짜 예약' 만들기 (Phase 3).

진짜 DB(data/gpu.db)는 절대 건드리지 않는다.
대신 backend/demo/ 폴더에 **데모 전용 설정과 DB**를 새로 만들고 거기에만 데이터를 넣는다.

쓰는 법 (backend 폴더에서):
    PYTHONPATH= venv/bin/python scripts/seed_demo.py

그다음 화면에 안내되는 대로 데모 설정으로 서버를 켜면,
타임라인에 여러 색깔의 예약이 보인다.

주의: 여기서는 예약 규칙 검사(과거 시작 금지 등)를 일부러 건너뛰고 DB에 직접 넣는다.
'지나간 예약(회색)'처럼 정상 경로로는 만들 수 없는 상황도 화면에서 확인해야 하기 때문이다.
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys
from datetime import datetime, timedelta
from pathlib import Path

import yaml

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent

DEMO_INVITE_CODE = "DEMO-CODE-1234"
DEMO_PASSWORD = "demo1234"


# ---------- 1) 데모 전용 설정 파일 만들기 ----------

def 데모설정만들기(demo_dir: Path) -> tuple[Path, Path]:
    """demo/config.yaml 과 demo/demo.db 경로를 준비한다.

    GPU 목록·규칙은 실제 설정(config.yaml, 없으면 config.example.yaml)에서 가져오고,
    가입 코드·JWT 비밀키·DB 경로는 데모 전용 값으로 덮어쓴다.
    (실제 비밀값은 데모 파일에 복사하지 않는다)
    """
    원본 = BACKEND_DIR / "config.yaml"
    if not 원본.exists():
        원본 = BACKEND_DIR / "config.example.yaml"
    raw = yaml.safe_load(원본.read_text(encoding="utf-8")) or {}

    db_path = demo_dir / "demo.db"
    raw.setdefault("app", {})
    raw["app"]["invite_code"] = DEMO_INVITE_CODE
    raw["app"]["jwt_secret"] = secrets.token_urlsafe(48)
    raw["app"]["database_path"] = str(db_path)
    raw.setdefault("google", {})
    raw["google"]["enabled"] = False

    demo_dir.mkdir(parents=True, exist_ok=True)
    config_path = demo_dir / "config.yaml"
    config_path.write_text(
        "# 이 파일은 scripts/seed_demo.py 가 자동으로 만든다. 직접 고칠 필요 없다.\n"
        "# 화면 확인용이라 가입 코드가 공개 값이므로, 실제 운영에는 쓰지 말 것.\n"
        + yaml.safe_dump(raw, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return config_path, db_path


def 안전검사(db_path: Path) -> None:
    """실수로 진짜 DB를 덮어쓰지 못하게 막는다 (CLAUDE.md 규칙)."""
    real_data_dir = (REPO_DIR / "data").resolve()
    resolved = db_path.resolve()
    if resolved.parent == real_data_dir or resolved.name == "gpu.db":
        print(
            f"중단했습니다: {resolved} 는 실제 DB 폴더입니다.\n"
            "데모 스크립트는 data/ 폴더를 건드리지 않습니다.",
            file=sys.stderr,
        )
        raise SystemExit(1)


# ---------- 2) 데모 데이터 ----------

# (GPU 분류, 그 분류 안에서 몇 번째 GPU인가, 예약자, 시작 offset(시간), 길이(시간), 상태)
# offset 은 '지금이 속한 정시' 기준. 음수면 과거.
데모예약 = [
    # --- 단주기 GPU 6장 ---
    ("short", 0, "김민준", -3, 8, "active"),      # 사용 중(노랑) → 뒤쪽은 미래
    ("short", 0, "이서연", 5, 4, "active"),       # 앞 예약과 딱 붙는 예약 (경계 허용)
    ("short", 1, "박도윤", -30, 10, "active"),    # 어제 끝난 예약 (회색)
    ("short", 1, "최지우", 26, 24, "active"),     # 이틀 뒤 예약 (빨강)
    # short[2] 는 일부러 비워 둔다 → 하루 종일 초록(예약 가능)
    ("short", 3, "정하윤", 2, 4, "cancelled"),    # 취소됨 → 타임라인에 보이면 안 된다
    ("short", 3, "정하윤", 48, 12, "active"),
    ("short", 4, "김민준", 6, 2, "active"),
    ("short", 4, "이서연", 12, 3, "active"),
    ("short", 4, "박도윤", 60, 6, "active"),
    ("short", 5, "최지우", 0, 48, "active"),      # 지금 시작, 48시간짜리

    # --- 장주기 GPU 6장 ---
    ("long", 0, "정하윤", -48, 168, "active"),    # 사용 중인 일주일짜리
    ("long", 1, "김민준", 240, 336, "active"),    # 표 오른쪽 끝을 넘어가는 예약 (잘려서 보임)
    ("long", 2, "이서연", 72, 96, "active"),
    ("long", 3, "박도윤", -90, 100, "active"),    # 표 왼쪽 끝(오늘 0시) 이전에 시작한 예약
    # long[4] 는 비워 둔다
    ("long", 5, "최지우", 24, 72, "active"),
    ("long", 5, "김민준", 96, 104, "active"),     # 바로 이어지는 예약
]

데모사용자 = [
    ("김민준", "minjun@example.com"),
    ("이서연", "seoyeon@example.com"),
    ("박도윤", "doyun@example.com"),
    ("최지우", "jiwoo@example.com"),
    ("정하윤", "hayun@example.com"),
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="타임라인 확인용 데모 DB와 예약 데이터를 만든다 (실제 DB는 건드리지 않음)."
    )
    parser.add_argument(
        "--dir",
        default=str(BACKEND_DIR / "demo"),
        help="데모 설정과 DB를 둘 폴더 (기본: backend/demo)",
    )
    args = parser.parse_args()

    demo_dir = Path(args.dir).resolve()
    config_path, db_path = 데모설정만들기(demo_dir)
    안전검사(db_path)

    # 이전에 만든 데모 DB는 지우고 처음부터 다시 만든다 (데모 폴더 안에서만)
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(db_path) + suffix)
        if p.exists():
            p.unlink()

    # app 모듈은 이 환경변수를 보고 설정 파일을 고르므로 import 전에 설정해야 한다
    os.environ["GPU_RESERVE_CONFIG"] = str(config_path)
    sys.path.insert(0, str(BACKEND_DIR))

    from app import timeutil
    from app.database import Base, SessionLocal, engine
    from app.models import Gpu, Reservation, User
    from app.security import hash_password
    from app.seed import seed_gpus

    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        seed_gpus(db)

        users: dict[str, User] = {}
        for name, email in 데모사용자:
            user = User(
                name=name,
                email=email,
                password_hash=hash_password(DEMO_PASSWORD),
                is_admin=False,
            )
            db.add(user)
            users[name] = user
        db.flush()

        gpus = db.query(Gpu).order_by(Gpu.sort_order).all()
        분류별 = {
            "short": [g for g in gpus if g.category == "short"],
            "long": [g for g in gpus if g.category == "long"],
        }

        기준 = timeutil.floor_hour(timeutil.now_kst())  # 지금이 속한 정시
        만든개수 = 0
        for category, idx, name, start_offset, length, status in 데모예약:
            gpu = 분류별[category][idx]
            start_at = 기준 + timedelta(hours=start_offset)
            db.add(
                Reservation(
                    gpu_id=gpu.id,
                    user_id=users[name].id,
                    start_at=start_at,
                    end_at=start_at + timedelta(hours=length),
                    status=status,
                )
            )
            만든개수 += 1

        db.commit()

    안내출력(config_path, db_path, 기준, 만든개수)


def 안내출력(config_path: Path, db_path: Path, 기준: datetime, 개수: int) -> None:
    rel_config = os.path.relpath(config_path, BACKEND_DIR)
    print()
    print("데모 데이터를 만들었습니다. (실제 DB data/gpu.db 는 건드리지 않았습니다)")
    print(f"  설정 파일 : {config_path}")
    print(f"  데모 DB   : {db_path}")
    print(f"  기준 시각 : {timeutil_format(기준)}")
    print(f"  예약 {개수}건 (취소된 예약 1건 포함 — 타임라인에는 보이면 안 됩니다)")
    print()
    print("이 데이터로 화면을 보려면 backend 폴더에서 (포트 9081 — 9080은 운영 서버가 쓴다):")
    print(f'  GPU_RESERVE_CONFIG={rel_config} PYTHONPATH= \\')
    print("    venv/bin/python -m uvicorn app.main:app --reload --port 9081")
    print()
    print("그다음 다른 터미널에서 frontend 의 `npm run dev` 를 켜고 http://localhost:5173 접속.")
    print("로그인 정보:")
    for name, email in 데모사용자:
        print(f"  {name}: {email} / 비밀번호 {DEMO_PASSWORD}")
    print(f"(새 계정을 만들고 싶으면 가입 코드는 {DEMO_INVITE_CODE})")
    print()


def timeutil_format(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M")


if __name__ == "__main__":
    main()
