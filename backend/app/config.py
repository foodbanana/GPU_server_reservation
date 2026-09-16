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
class CategoryRule:
    """단주기/장주기 각각의 최소·최대 예약 시간(시간 단위)."""

    min_hours: int
    max_hours: int


@dataclass(frozen=True)
class Rules:
    slot_minutes: int
    booking_horizon_days: int
    short: CategoryRule
    long: CategoryRule

    def for_category(self, category: str) -> CategoryRule:
        return self.short if category == "short" else self.long


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

    # database_path 는 설정 파일 위치를 기준으로 한 상대경로로 해석한다.
    db_path = Path(app_raw.get("database_path", "../data/gpu.db"))
    if not db_path.is_absolute():
        db_path = (path.resolve().parent / db_path).resolve()

    def category_rule(name: str, default_min: int, default_max: int) -> CategoryRule:
        node = rules_raw.get(name, {}) or {}
        return CategoryRule(
            min_hours=int(node.get("min_hours", default_min)),
            max_hours=int(node.get("max_hours", default_max)),
        )

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
        rules=Rules(
            slot_minutes=int(rules_raw.get("slot_minutes", 60)),
            booking_horizon_days=int(rules_raw.get("booking_horizon_days", 14)),
            short=category_rule("short", 1, 48),
            long=category_rule("long", 48, 336),
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
