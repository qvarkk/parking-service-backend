from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base
import enum
from sqlalchemy import Enum as SQLEnum


class CameraStatus(str, enum.Enum):
    ok = "ok"
    camera_unreachable = "camera_unreachable"
    unknown = "unknown"


class TripStatus(str, enum.Enum):
    active = "active"
    completed = "completed"
    expired = "expired"
    cancelled = "cancelled"


class TestCamera(Base):
    __tablename__ = "test_cameras"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    status = Column(SQLEnum(CameraStatus), default=CameraStatus.unknown)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    snapshots = relationship("TestSnapshot", back_populates="camera")
    sessions = relationship("TripSession", back_populates="camera")


class TestSnapshot(Base):
    __tablename__ = "test_snapshots"
    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, ForeignKey("test_cameras.id"))
    free_spots_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    camera = relationship("TestCamera", back_populates="snapshots")


class UserRequest(Base):
    __tablename__ = "user_requests"
    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, ForeignKey("test_cameras.id"), nullable=True)
    query_address = Column(String, nullable=True)
    lat = Column(Float, nullable=True)
    lon = Column(Float, nullable=True)
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    is_success = Column(Boolean, default=False)
    error_code = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class TripSession(Base):
    __tablename__ = "trip_sessions"
    id = Column(Integer, primary_key=True, index=True)
    target_camera_id = Column(Integer, ForeignKey("test_cameras.id"))
    status = Column(SQLEnum(TripStatus), default=TripStatus.active)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    device_token = Column(String, nullable=True)

    notifications = relationship("TripNotification", back_populates="session")
    camera = relationship("TestCamera", back_populates="sessions")


class TripNotification(Base):
    __tablename__ = "trip_notifications"
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("trip_sessions.id"))
    message = Column(String, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("TripSession", back_populates="notifications")


class AdminUser(Base):
    __tablename__ = "admin_users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    is_active = Column(Boolean, default=True)


class BlacklistedToken(Base):
    __tablename__ = "blacklisted_tokens"
    id = Column(Integer, primary_key=True, index=True)
    jti = Column(String, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, index=True)
    token = Column(String, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
