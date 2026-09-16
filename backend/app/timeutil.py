"""한국 시간(KST) 처리 도구.

- DB에는 KST 기준 '시간대 정보 없는(naive)' datetime 으로 저장한다(PLAN 확정사항).
- API로 주고받을 때는 +09:00 이 붙은 ISO8601 문자열을 쓴다.
- 테스트에서 시간을 고정할 수 있도록 현재 시각은 항상 now_kst() 로만 구한다.
  (다른 모듈은 `from app import timeutil` 후 `timeutil.now_kst()` 로 부를 것)
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")


def now_kst() -> datetime:
    """지금 시각 (KST, 시간대 정보 없음)."""
    return datetime.now(KST).replace(tzinfo=None)


def as_aware(dt: datetime) -> datetime:
    """DB에서 꺼낸 naive datetime 에 +09:00 을 붙여 준다 (API 응답용)."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=KST)
    return dt.astimezone(KST)


def to_naive_kst(dt: datetime) -> datetime:
    """API로 들어온 시각을 KST 기준 naive datetime 으로 바꾼다.

    시간대가 없으면 이미 KST라고 본다.
    """
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(KST).replace(tzinfo=None)


def floor_hour(dt: datetime) -> datetime:
    """정시 내림. 14:20 -> 14:00"""
    return dt.replace(minute=0, second=0, microsecond=0)


def ceil_hour(dt: datetime) -> datetime:
    """정시 올림. 14:20 -> 15:00, 14:00 -> 14:00"""
    floored = floor_hour(dt)
    if floored == dt:
        return dt
    return floored + timedelta(hours=1)


def is_on_the_hour(dt: datetime) -> bool:
    """분·초가 0인 정시인지."""
    return dt.minute == 0 and dt.second == 0 and dt.microsecond == 0


def format_kst(dt: datetime) -> str:
    """오류 메시지에 넣을 사람이 읽기 좋은 형식. 2026-01-05 14:00"""
    return dt.strftime("%Y-%m-%d %H:%M")
