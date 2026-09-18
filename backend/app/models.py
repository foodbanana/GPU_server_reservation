"""DB 테이블 정의 (PLAN 3장)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app import timeutil
from app.database import Base

STATUS_ACTIVE = "active"
STATUS_CANCELLED = "cancelled"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: timeutil.now_kst()
    )

    reservations: Mapped[list["Reservation"]] = relationship(back_populates="user")


class Gpu(Base):
    __tablename__ = "gpus"
    __table_args__ = (UniqueConstraint("server_no", "gpu_index", name="uq_gpu_slot"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    server_no: Mapped[int] = mapped_column(Integer, nullable=False)
    gpu_index: Mapped[int] = mapped_column(Integer, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)  # short / long
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    reservations: Mapped[list["Reservation"]] = relationship(back_populates="gpu")

    @property
    def category_label(self) -> str:
        return "단주기" if self.category == "short" else "장주기"

    @property
    def label(self) -> str:
        """화면·오류 메시지에 쓰는 이름. 예: 서버1 GPU2 (A6000, 장주기)"""
        return (
            f"서버{self.server_no} GPU{self.gpu_index} "
            f"({self.model}, {self.category_label})"
        )


class Reservation(Base):
    __tablename__ = "reservations"
    __table_args__ = (
        Index("ix_res_gpu_time", "gpu_id", "start_at", "end_at"),
        Index("ix_res_user", "user_id"),
        Index("ix_res_status", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gpu_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("gpus.id"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    # KST 기준, 항상 정시(분·초 0)
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    # 취소해도 행을 지우지 않고 status 만 바꾼다 (기록 보존)
    status: Mapped[str] = mapped_column(
        String, nullable=False, default=STATUS_ACTIVE
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: timeutil.now_kst()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=lambda: timeutil.now_kst(), onupdate=lambda: timeutil.now_kst()
    )
    google_event_id: Mapped[str | None] = mapped_column(String, nullable=True)

    gpu: Mapped["Gpu"] = relationship(back_populates="reservations")
    user: Mapped["User"] = relationship(back_populates="reservations")

    @property
    def user_name(self) -> str:
        return self.user.name if self.user else ""

    @property
    def user_email(self) -> str:
        """관리자 화면에서만 쓴다 (일반 사용자 응답에는 넣지 않는다)."""
        return self.user.email if self.user else ""

    @property
    def gpu_label(self) -> str:
        return self.gpu.label if self.gpu else ""


# ---------------------------------------------------------------------------
# Postgres 전용: 시간이 겹치는 예약을 DB가 직접 거부하게 하는 제약
# ---------------------------------------------------------------------------
# SQLite 에서는 database.py 의 BEGIN IMMEDIATE 잠금이 이 역할을 한다.
# Postgres 에는 그런 잠금이 없어서, 두 사람이 동시에 신청하면
# 둘 다 "겹치는 예약 없음"을 보고 둘 다 저장해 버릴 수 있다.
# 그래서 테이블 자체에 "같은 GPU + 시간 겹침" 을 금지하는 제약(EXCLUDE)을 건다.
# 이러면 파이썬 코드가 어떻게 돌든 DB가 마지막에 막아 준다.
#
# 참고 1) `WHERE (status = 'active')` — 취소된 예약은 검사하지 않는다.
#         그래야 취소한 시간을 다른 사람이 다시 예약할 수 있다.
# 참고 2) `tstzrange(...)` 안에 `timezone('Asia/Seoul', ...)` 를 감싼 이유:
#         우리 DB의 start_at / end_at 은 시간대 정보가 없는 값(KST 기준)이다
#         (timeutil.py 참고). Postgres 가 이걸 알아서 시간대 있는 값으로 바꾸게 두면
#         "서버 시간대 설정에 따라 결과가 달라지는 계산"이 되어 제약에 쓸 수 없다.
#         `timezone('Asia/Seoul', ...)` 로 시간대를 못 박아 주면 항상 같은 결과가
#         나오므로 제약에 쓸 수 있다. (한국은 서머타임이 없어 단순 +09:00 이다)
# 참고 3) `[start_at, end_at)` — 시작은 포함, 종료는 제외. 그래서 10시 종료와
#         10시 시작은 겹치지 않는다 (SPEC 5장의 겹침 정의와 같다).

#: 제약 이름. 오류 메시지에서 "겹침 때문에 거부됐다"를 알아보는 데도 쓴다.
OVERLAP_CONSTRAINT = "reservations_no_overlap"

_CREATE_OVERLAP_CONSTRAINT_SQL = f"""
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = '{OVERLAP_CONSTRAINT}'
    ) THEN
        ALTER TABLE reservations
            ADD CONSTRAINT {OVERLAP_CONSTRAINT}
            EXCLUDE USING gist (
                gpu_id WITH =,
                tstzrange(
                    timezone('Asia/Seoul', start_at),
                    timezone('Asia/Seoul', end_at)
                ) WITH &&
            ) WHERE (status = '{STATUS_ACTIVE}');
    END IF;
END
$$;
"""


def ensure_overlap_constraint(bind) -> None:  # noqa: ANN001
    """Postgres 라면 겹침 금지 제약을 만든다. SQLite 면 아무것도 하지 않는다.

    테이블을 만든 뒤에 한 번 불러 주면 된다(main.py, tests/conftest.py).
    이미 제약이 있으면 그냥 넘어가므로 여러 번 불러도 괜찮다.
    """
    if bind.dialect.name != "postgresql":
        return

    with bind.begin() as conn:
        # gist 인덱스에서 정수(gpu_id)를 `=` 로 비교하려면 이 확장이 필요하다.
        conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS btree_gist")
        conn.exec_driver_sql(_CREATE_OVERLAP_CONSTRAINT_SQL)
