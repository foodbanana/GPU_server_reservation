"""API 요청·응답 데이터 형식 (Pydantic).

시간은 모두 +09:00 이 붙은 ISO8601 문자열로 주고받는다.
예: "2026-01-05T14:00:00+09:00"
"""

from __future__ import annotations

from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_serializer,
    model_validator,
)

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


class ConfigOut(BaseModel):
    """프론트엔드가 쓸 설정값.

    예약 길이 제한과 '14일 이내 시작' 제한이 없어졌으므로 규칙값은 slot_minutes 뿐이다.
    timeline_days 는 예약 제한이 아니라 타임라인이 한 번에 보여 주는 일수다.
    """

    timezone: str
    slot_minutes: int
    timeline_days: int


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


class AdminUserOut(BaseModel):
    """관리자 화면의 가입자 목록용 (보기 전용).

    비밀번호 해시는 절대 담지 않는다. 이 스키마에 필드가 없으므로
    response_model 을 거치면서 자동으로 걸러진다.
    """

    id: int
    name: str
    email: EmailStr
    is_admin: bool
    # 이 사람이 '아무도 관리자에서 해제할 수 없는' 최고 관리자인가.
    # 환경변수 GPU_RESERVE_SUPER_ADMIN_EMAIL 로 정한다(없으면 모두 False).
    # 화면에서 해제 버튼을 감추는 데 쓴다. 실제 차단은 서버가 한다.
    is_super_admin: bool = False
    created_at: datetime
    # 지금 사용 중이거나 앞으로 예정된 예약 수 (취소·종료된 예약은 세지 않는다)
    active_reservation_count: int

    @field_serializer("created_at")
    def _with_kst_offset(self, value: datetime) -> datetime:
        return timeutil.as_aware(value)


class AdminRoleUpdate(BaseModel):
    """관리자 권한을 주거나 뺏는 요청.

    대상은 user_id 또는 email 중 **하나만** 준다.
    (화면은 목록에 있는 user_id 를 쓰고, 터미널·직접 호출은 email 이 편하다)
    """

    is_admin: bool
    user_id: int | None = None
    email: EmailStr | None = None

    @model_validator(mode="after")
    def _대상은_하나만(self) -> "AdminRoleUpdate":
        if (self.user_id is None) == (self.email is None):
            raise ValueError("user_id 와 email 중 정확히 하나만 지정해 주세요.")
        return self


class AdminRoleResult(BaseModel):
    """권한 변경 결과. 화면이 그대로 보여 줄 수 있는 한국어 메시지를 함께 준다."""

    # promoted / revoked / already_admin / already_normal
    result: str
    user_id: int
    name: str
    email: EmailStr
    is_admin: bool
    message: str
