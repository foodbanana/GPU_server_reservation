"""config.yaml 을 읽어서 파이썬 객체로 바꿔 준다.

설정값을 코드에 직접 박지 않기 위한 파일이다(SPEC 3장).
환경변수 GPU_RESERVE_CONFIG 로 다른 설정 파일을 지정할 수 있다(테스트에서 사용).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = BACKEND_DIR / "config.yaml"


@dataclass(frozen=True)
class Rules:
    """예약 규칙.

    예약 길이 제한(단주기 최대·장주기 최소 등)과 '14일 이내 시작' 제한은
    연구실에서 협의해 쓰기로 하여 없앴다. 남은 규칙은 코드에 고정된
    '1시간 단위 / 종료가 시작보다 뒤 / 지난 시각 금지 / 같은 GPU 겹침 금지' 뿐이다.

    timeline_days 는 예약 제한이 아니라 **타임라인 화면이 한 번에 보여 주는 일수**다.
    (화면에서 '이전/다음' 버튼으로 이 일수만큼 앞뒤로 옮겨 본다)
    """

    slot_minutes: int
    timeline_days: int


@dataclass(frozen=True)
class GpuSpec:
    server_no: int
    gpu_index: int
    model: str
    category: str  # "short"(단주기) 또는 "long"(장주기)


@dataclass(frozen=True)
class Config:
    timezone: str
    invite_code: str
    jwt_secret: str
    jwt_expire_days: int
    database_path: Path
    static_dir: Path | None
    rules: Rules
    gpus: tuple[GpuSpec, ...]
    google_enabled: bool


def _config_path() -> Path:
    return Path(os.environ.get("GPU_RESERVE_CONFIG", DEFAULT_CONFIG_PATH))


def load_config(path: Path | None = None) -> Config:
    path = Path(path) if path is not None else _config_path()
    if not path.exists():
        raise RuntimeError(
            f"설정 파일이 없습니다: {path}\n"
            "backend 폴더에서 `cp config.example.yaml config.yaml` 을 실행한 뒤 값을 채워 주세요."
        )

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    app_raw = raw.get("app", {})
    rules_raw = raw.get("rules", {})
    gpus_raw = raw.get("gpus", []) or []

    for key in ("invite_code", "jwt_secret"):
        if not app_raw.get(key):
            raise RuntimeError(f"{path} 의 app.{key} 값이 비어 있습니다. 값을 채워 주세요.")

    if len(gpus_raw) == 0:
        raise RuntimeError(f"{path} 의 gpus 목록이 비어 있습니다.")

    # database_path / static_dir 는 설정 파일 위치를 기준으로 한 상대경로로 해석한다.
    base_dir = path.resolve().parent

    def resolve(value: str) -> Path:
        p = Path(value)
        return p if p.is_absolute() else (base_dir / p).resolve()

    db_path = resolve(str(app_raw.get("database_path", "../data/gpu.db")))

    # static_dir: Vue 를 빌드한 결과 폴더(frontend/dist). 이걸 FastAPI 가 함께 서빙해서
    # 포트 하나(9080)로 화면과 API를 모두 제공한다(Phase 5, SPEC 10장).
    # 빈 값("" 또는 null)으로 두면 정적 파일을 서빙하지 않는다(개발용 설정에서 사용).
    static_raw = app_raw.get("static_dir", "../frontend/dist")
    static_dir = resolve(str(static_raw)) if static_raw else None

    gpus = tuple(
        GpuSpec(
            server_no=int(g["server_no"]),
            gpu_index=int(g["gpu_index"]),
            model=str(g["model"]),
            category=str(g["category"]),
        )
        for g in gpus_raw
    )
    for gpu in gpus:
        if gpu.category not in ("short", "long"):
            raise RuntimeError(
                f"GPU 설정의 category 는 short 또는 long 이어야 합니다: {gpu}"
            )

    return Config(
        timezone=str(app_raw.get("timezone", "Asia/Seoul")),
        invite_code=str(app_raw["invite_code"]),
        jwt_secret=str(app_raw["jwt_secret"]),
        jwt_expire_days=int(app_raw.get("jwt_expire_days", 30)),
        database_path=db_path,
        static_dir=static_dir,
        rules=Rules(
            slot_minutes=int(rules_raw.get("slot_minutes", 60)),
            timeline_days=int(rules_raw.get("timeline_days", 14)),
        ),
        gpus=gpus,
        google_enabled=bool((raw.get("google", {}) or {}).get("enabled", False)),
    )


_config: Config | None = None


def get_config() -> Config:
    """설정을 한 번만 읽고 재사용한다."""
    global _config
    if _config is None:
        _config = load_config()
    return _config
