from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, Enum, ForeignKey, Integer, String, Text
from app.db import Base


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    USER = "USER"


class RequestStatus(str, enum.Enum):
    RQ = "RQ"
    OP = "OP"
    RP = "RP"


class AssetStatus(str, enum.Enum):
    INV = "INV"
    READY = "READY"
    USE = "USE"
    RET = "RET"
    IT = "IT"
    DIS = "DIS"
    AUD = "AUD"
    LOST = "LOST"


class PlanStatus(str, enum.Enum):
    PLANNED = "PLANNED"
    DONE = "DONE"
    CANCELLED = "CANCELLED"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(64), unique=True, nullable=False)
    passcode_hash = Column(String(255), nullable=False)
    display_name = Column(String(128), nullable=False)
    role = Column(Enum(UserRole, native_enum=False), nullable=False, default=UserRole.USER)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class PcRequest(Base):
    __tablename__ = "pc_requests"

    id = Column(Integer, primary_key=True, index=True)
    status = Column(Enum(RequestStatus, native_enum=False), nullable=False)
    requester = Column(String(128), nullable=True)
    note = Column(Text, nullable=True)
    asset_id = Column(Integer, ForeignKey("pc_assets.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )



class PcAsset(Base):
    __tablename__ = "pc_assets"

    id = Column(Integer, primary_key=True, index=True)
    asset_tag = Column(String(50), unique=True, nullable=False)
    serial_no = Column(String(128), unique=True, nullable=True)
    hostname = Column(String(63), nullable=True)
    status = Column(Enum(AssetStatus, native_enum=False), nullable=False)
    current_user = Column(String(128), nullable=True)
    location = Column(String(128), nullable=True)
    request_id = Column(Integer, ForeignKey("pc_requests.id"), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )



class PcStatusHistory(Base):
    __tablename__ = "pc_status_history"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(16), nullable=False)
    entity_id = Column(Integer, nullable=False)
    from_status = Column(String(16), nullable=True)
    to_status = Column(String(16), nullable=False)
    changed_by = Column(String(64), nullable=False)
    reason = Column(String(1000), nullable=True)
    ticket_no = Column(String(64), nullable=True)
    changed_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))


class PcPlan(Base):
    __tablename__ = "pc_plans"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(16), nullable=False)
    entity_id = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    planned_date = Column(Date, nullable=True)
    planned_owner = Column(String(128), nullable=True)
    plan_status = Column(Enum(PlanStatus, native_enum=False), nullable=False, default=PlanStatus.PLANNED)
    actual_date = Column(Date, nullable=True)
    actual_owner = Column(String(128), nullable=True)
    result_note = Column(Text, nullable=True)
    created_by = Column(String(64), nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
