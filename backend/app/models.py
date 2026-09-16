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
    def gpu_label(self) -> str:
        return self.gpu.label if self.gpu else ""
