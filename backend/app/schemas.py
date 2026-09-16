"""API 요청·응답 데이터 형식 (Pydantic).

시간은 모두 +09:00 이 붙은 ISO8601 문자열로 주고받는다.
예: "2026-01-05T14:00:00+09:00"
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_serializer

from app import timeutil


# ---------- 인증 ----------
class SignupRequest(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    email: EmailStr
    # 비밀번호 길이 제한은 두지 않는다. 다만 빈 값과 bcrypt 한계(72바이트) 초과는
    # routers/auth.py 에서 한국어 메시지와 함께 막는다.
    password: str
    invite_code: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    is_admin: bool


# ---------- GPU / 설정 ----------
class GpuOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    server_no: int
    gpu_index: int
    model: str
    category: str
    category_label: str
    sort_order: int
    label: str


class CategoryRuleOut(BaseModel):
    min_hours: int
    max_hours: int


class ConfigOut(BaseModel):
    """프론트엔드가 쓸 규칙값 (편의용 검사에 사용)."""

    timezone: str
    slot_minutes: int
    booking_horizon_days: int
    short: CategoryRuleOut
    long: CategoryRuleOut


# ---------- 예약 ----------
class ReservationCreate(BaseModel):
    gpu_id: int
    start_at: datetime
    end_at: datetime


class ReservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    gpu_id: int
    user_id: int
    user_name: str
    gpu_label: str
    start_at: datetime
    end_at: datetime
    status: str

    @field_serializer("start_at", "end_at")
    def _with_kst_offset(self, value: datetime) -> datetime:
        # DB에는 시간대 없이 저장되어 있으므로 응답에서 +09:00 을 붙여 준다.
        return timeutil.as_aware(value)


# ---------- 관리자 (Phase 4) ----------
class ReservationTimeUpdate(BaseModel):
    """관리자 수정 요청. 시작·종료 시각만 바꿀 수 있다(PLAN 확정사항).

    GPU와 예약자는 바꿀 수 없으므로 아예 받지 않는다.
    """

    start_at: datetime
    end_at: datetime


class AdminReservationOut(ReservationOut):
    """관리자 목록용. 누구 예약인지 구분할 수 있게 이메일을 더 준다."""

    user_email: str


class AdminUpdateResult(BaseModel):
    """관리자 수정 결과.

    warnings 에는 관리자가 무시하고 저장한 규칙 설명이 담긴다.
    (예: "단주기 예약 시간 제한(1~48시간)을 무시하고 저장했습니다.")
    """

    reservation: AdminReservationOut
    warnings: list[str] = []
