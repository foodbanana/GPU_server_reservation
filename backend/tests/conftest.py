"""테스트 공통 준비물.

- 테스트 전용 config.yaml 과 임시 DB 파일을 만든다 (진짜 DB를 건드리지 않는다).
- 현재 시각을 마음대로 고정할 수 있게 timeutil.now_kst 를 바꿔치기한다.

**어떤 DB로 테스트하나**
환경변수 `DATABASE_URL` 이 있으면 그 Postgres 로, 없으면 임시 폴더의 SQLite 파일로
테스트한다(app/database.py 가 그렇게 고르기 때문에 여기서 따로 할 일은 없다).

    PYTHONPATH= venv/bin/python -m pytest                      # SQLite
    DATABASE_URL='...' PYTHONPATH= venv/bin/python -m pytest    # Postgres

주의: Postgres 로 돌리면 테스트마다 **그 DB의 테이블을 모두 지우고 다시 만든다.**
반드시 테스트 전용 DB 주소를 넣어야 한다. 진짜 데이터가 든 DB를 넣으면 안 된다.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# ---- app 모듈을 import 하기 "전에" 테스트용 설정 파일을 준비해야 한다 ----
_TMP_DIR = Path(tempfile.mkdtemp(prefix="gpu-reserve-test-"))
TEST_INVITE_CODE = "TEST-CODE-1234"

_TEST_CONFIG = f"""
app:
  timezone: "Asia/Seoul"
  invite_code: "{TEST_INVITE_CODE}"
  jwt_secret: "test-secret-do-not-use-in-production"
  jwt_expire_days: 30
  database_path: "{_TMP_DIR / 'test.db'}"

rules:
  slot_minutes: 60
  timeline_days: 14

gpus:
  - {{ server_no: 1, gpu_index: 0, model: "A6000",     category: short }}
  - {{ server_no: 1, gpu_index: 1, model: "A6000",     category: short }}
  - {{ server_no: 1, gpu_index: 2, model: "A6000",     category: long  }}
  - {{ server_no: 1, gpu_index: 3, model: "A6000",     category: long  }}
  - {{ server_no: 2, gpu_index: 0, model: "RTX 3090",  category: short }}
  - {{ server_no: 2, gpu_index: 1, model: "RTX 3090",  category: short }}
  - {{ server_no: 2, gpu_index: 2, model: "RTX 3090",  category: long  }}
  - {{ server_no: 2, gpu_index: 3, model: "RTX 3090",  category: long  }}
  - {{ server_no: 3, gpu_index: 0, model: "A100",      category: short }}
  - {{ server_no: 3, gpu_index: 1, model: "A100",      category: long  }}
  - {{ server_no: 3, gpu_index: 2, model: "maxQ 6000", category: short }}
  - {{ server_no: 3, gpu_index: 3, model: "maxQ 6000", category: long  }}

google:
  enabled: false
"""

_CONFIG_PATH = _TMP_DIR / "config.yaml"
_CONFIG_PATH.write_text(_TEST_CONFIG, encoding="utf-8")
os.environ["GPU_RESERVE_CONFIG"] = str(_CONFIG_PATH)

# 여기서부터 app 모듈 import (위에서 환경변수를 설정한 뒤여야 한다)
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app import timeutil  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import User, ensure_overlap_constraint  # noqa: E402
from app.seed import seed_gpus  # noqa: E402

# 테스트에서 쓰는 '고정된 현재 시각': 2026년 1월 5일 월요일 14시 20분
DEFAULT_NOW = datetime(2026, 1, 5, 14, 20, 0)


class FakeClock:
    """테스트 안에서 현재 시각을 고정하거나 바꾸는 도구."""

    def __init__(self, now: datetime) -> None:
        self.now = now

    def set(self, now: datetime) -> None:
        self.now = now

    def hour(self, offset_hours: int) -> datetime:
        """고정 시각이 속한 정시에서 offset_hours 시간 뒤의 정시."""
        return timeutil.floor_hour(self.now) + timedelta(hours=offset_hours)


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> FakeClock:
    """현재 시각을 2026-01-05 14:20 으로 고정한다."""
    fake = FakeClock(DEFAULT_NOW)
    monkeypatch.setattr(timeutil, "now_kst", lambda: fake.now)
    return fake


@pytest.fixture
def db_session():
    """테스트마다 빈 DB로 시작한다."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    # Postgres 면 '시간 겹침 금지' 제약을 다시 걸어 준다 (SQLite 면 아무 일도 안 한다).
    # 운영에서 main.py 가 하는 일과 같다.
    ensure_overlap_constraint(engine)
    with SessionLocal() as session:
        seed_gpus(session)
        yield session


@pytest.fixture
def client(db_session, clock) -> TestClient:
    """lifespan 없이 앱을 띄운다 (테이블·GPU는 db_session 픽스처가 준비함)."""
    with TestClient(app) as test_client:
        yield test_client


# ---------- 테스트에서 자주 쓰는 도우미 ----------

def iso(dt: datetime) -> str:
    """KST(+09:00)가 붙은 ISO8601 문자열로."""
    return dt.replace(tzinfo=timeutil.KST).isoformat()


def signup(client: TestClient, email: str, name: str = "홍길동", password: str = "test-pw-1234") -> dict:
    response = client.post(
        "/api/auth/signup",
        json={
            "name": name,
            "email": email,
            "password": password,
            "invite_code": TEST_INVITE_CODE,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def login_headers(client: TestClient, email: str, password: str = "test-pw-1234") -> dict:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def auth_headers(client: TestClient, email: str = "user@example.com", name: str = "홍길동") -> dict:
    """가입 + 로그인 한 번에."""
    signup(client, email=email, name=name)
    return login_headers(client, email=email)


def gpu_id_by(client: TestClient, headers: dict, category: str) -> int:
    """단주기('short') 또는 장주기('long') GPU 하나의 id."""
    response = client.get("/api/gpus", headers=headers)
    assert response.status_code == 200, response.text
    for gpu in response.json():
        if gpu["category"] == category:
            return gpu["id"]
    raise AssertionError(f"{category} GPU를 찾지 못했습니다.")


def create_reservation(
    client: TestClient, headers: dict, gpu_id: int, start: datetime, end: datetime
):
    return client.post(
        "/api/reservations",
        headers=headers,
        json={"gpu_id": gpu_id, "start_at": iso(start), "end_at": iso(end)},
    )


def make_admin(email: str) -> None:
    """가입한 계정을 관리자로 올린다 (scripts/create_admin.py 가 하는 일과 같다)."""
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email.lower()))
        assert user is not None, f"{email} 계정이 없습니다."
        user.is_admin = True
        db.commit()


def admin_headers(
    client: TestClient, email: str = "admin@example.com", name: str = "관리자"
) -> dict:
    """관리자 계정으로 가입 + 권한 부여 + 로그인."""
    signup(client, email=email, name=name)
    make_admin(email)
    return login_headers(client, email=email)
