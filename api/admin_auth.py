from datetime import datetime
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import func
from sqlalchemy.orm import Session
from database import get_db
from models.core import (
    UserRequest,
    TestSnapshot,
    AdminUser,
    TestCamera,
    BlacklistedToken,
    PasswordResetToken,
    TripSession,
    TripNotification,
)
from schemas.auth import (
    Token,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    CaptchaConfigResponse,
)
from schemas.parking import (
    AdminCameraResponse,
    AdminCameraCreate,
    AdminCameraStatusUpdate,
    AdminTripNotificationRequest,
)
from api.utils import get_client_ip
from services import auth, email as email_service, smartcaptcha
from services.notification import notifier
from config import settings
from jose import JWTError, jwt
from datetime import datetime, timedelta
from api.limiter import limiter

router = APIRouter(tags=["Admin API"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


async def get_current_admin(
    db: Session = Depends(get_db), token: str = Depends(oauth2_scheme)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        email: str = payload.get("sub")
        jti: str = payload.get("jti")
        if email is None or jti is None:
            raise credentials_exception

        is_blacklisted = (
            db.query(BlacklistedToken).filter(BlacklistedToken.jti == jti).first()
        )
        if is_blacklisted:
            raise credentials_exception

    except JWTError as exc:
        raise credentials_exception from exc

    admin = db.query(AdminUser).filter(AdminUser.email == email).first()
    if admin is None:
        raise credentials_exception
    return admin


@router.post("/auth/login", response_model=Token)
@limiter.limit("5/minute")
def login(
    request: Request,
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
    captcha_token: Annotated[Optional[str], Form()] = None,
):
    smartcaptcha.require_valid_captcha(captcha_token, get_client_ip(request))

    admin = db.query(AdminUser).filter(AdminUser.email == form_data.username).first()
    if not admin or not auth.verify_password(form_data.password, admin.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = auth.create_access_token(data={"sub": admin.email})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/admin/stats/requests")
def get_requests_stats(
    db: Session = Depends(get_db), current_admin: AdminUser = Depends(get_current_admin)
):
    now = datetime.utcnow()
    start_time = now - timedelta(hours=11)
    current_hour_start = now.replace(minute=0, second=0, microsecond=0)

    stats = []
    for i in range(11, -1, -1):
        hour_dt = current_hour_start - timedelta(hours=i)
        stats.append(
            {
                "hour": hour_dt.strftime("%H:00"),
                "request_count": 0,
                "_dt": hour_dt,
            }
        )

    requests = db.query(UserRequest).filter(UserRequest.created_at >= start_time).all()

    for req in requests:
        req_dt = req.created_at.replace(tzinfo=None, minute=0, second=0, microsecond=0)
        for item in stats:
            if item["_dt"] == req_dt:
                item["request_count"] += 1
                break

    for item in stats:
        del item["_dt"]

    return stats


@router.get("/admin/stats/availability")
def get_availability_stats(
    db: Session = Depends(get_db), current_admin: AdminUser = Depends(get_current_admin)
):
    cameras = db.query(TestCamera).all()
    total_currently_free = 0
    for cam in cameras:
        latest = (
            db.query(TestSnapshot)
            .filter(TestSnapshot.camera_id == cam.id)
            .order_by(TestSnapshot.created_at.desc())
            .first()
        )
        if latest:
            total_currently_free += latest.free_spots_count

    now = datetime.utcnow()
    current_hour_start = now.replace(minute=0, second=0, microsecond=0)

    hourly_trend = []
    for i in range(9, -1, -1):
        h_start = current_hour_start - timedelta(hours=i)
        h_end = h_start + timedelta(hours=1)

        avg_free = (
            db.query(func.avg(TestSnapshot.free_spots_count))
            .filter(TestSnapshot.created_at >= h_start, TestSnapshot.created_at < h_end)
            .scalar()
        )

        hourly_trend.append(
            {
                "hour": h_start.strftime("%H:00"),
                "free_spots": round(float(avg_free), 1) if avg_free is not None else 0,
            }
        )

    return {"current_total_free": total_currently_free, "hourly_trend": hourly_trend}


@router.get("/admin/cameras", response_model=list[AdminCameraResponse])
def get_admin_cameras(
    db: Session = Depends(get_db), current_admin: AdminUser = Depends(get_current_admin)
):
    cameras = db.query(TestCamera).all()

    for cam in cameras:
        cam.latest_snapshot = (
            db.query(TestSnapshot)
            .filter(TestSnapshot.camera_id == cam.id)
            .order_by(TestSnapshot.created_at.desc())
            .first()
        )

    return cameras


@router.post("/admin/cameras", response_model=AdminCameraResponse)
def create_admin_camera(
    data: AdminCameraCreate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    new_camera = TestCamera(
        name=data.name, lat=data.lat, lon=data.lon, status=data.status
    )
    db.add(new_camera)
    db.commit()
    db.refresh(new_camera)
    return new_camera


@router.post("/admin/cameras/{camera_id}/status", response_model=AdminCameraResponse)
def update_camera_status(
    camera_id: int,
    data: AdminCameraStatusUpdate,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    camera = db.query(TestCamera).filter(TestCamera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    camera.status = data.status
    db.commit()

    camera.latest_snapshot = (
        db.query(TestSnapshot)
        .filter(TestSnapshot.camera_id == camera.id)
        .order_by(TestSnapshot.created_at.desc())
        .first()
    )

    return camera


@router.get("/auth/captcha-config", response_model=CaptchaConfigResponse)
def get_captcha_config():
    site = (settings.SMARTCAPTCHA_SITE_KEY or "").strip()
    return CaptchaConfigResponse(
        site_key=site,
        enabled=smartcaptcha.is_enabled() and bool(site),
    )


@router.post("/auth/bootstrap-admin")
@limiter.limit("1/minute")
def bootstrap_admin(request: Request, db: Session = Depends(get_db)):
    admin_exists = db.query(AdminUser).first()

    if admin_exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin already exists. Bootstrapping is only allowed for fresh installations.",
        )

    default_admin = AdminUser(
        email="admin@example.com",
        hashed_password=auth.get_password_hash("admin123"),
        is_active=True,
    )

    db.add(default_admin)
    db.commit()
    db.refresh(default_admin)

    return {
        "status": "ok",
        "message": "Admin bootstrapped successfully",
        "email": default_admin.email,
        "note": "Use 'admin123' as password",
    }


@router.post("/auth/logout")
def logout(
    db: Session = Depends(get_db),
    token: str = Depends(oauth2_scheme),
    current_admin: AdminUser = Depends(get_current_admin),
):
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        jti = payload.get("jti")
        exp = payload.get("exp")

        if jti and exp:
            expires_at = datetime.fromtimestamp(exp)
            blacklisted_token = BlacklistedToken(jti=jti, expires_at=expires_at)
            db.add(blacklisted_token)
            db.commit()
    except JWTError:
        pass

    return {"status": "ok", "message": "Successfully logged out"}


@router.get("/auth/me")
def get_me_mock(current_admin: AdminUser = Depends(get_current_admin)):
    return {"email": current_admin.email, "is_active": current_admin.is_active}


@router.post("/auth/forgot-password")
@limiter.limit("3/hour")
def forgot_password(
    request: Request, data: ForgotPasswordRequest, db: Session = Depends(get_db)
):
    admin = db.query(AdminUser).filter(AdminUser.email == data.email).first()
    if not admin:
        return {"status": "ok", "message": "Reset link sent"}

    token = auth.create_reset_token(admin.email)
    expires_at = datetime.utcnow() + timedelta(minutes=30)

    reset_token = PasswordResetToken(
        email=admin.email, token=token, expires_at=expires_at
    )
    db.add(reset_token)
    db.commit()

    email_service.send_reset_password_email(admin.email, token)

    return {"status": "ok", "message": "Reset link sent"}


@router.post("/auth/reset-password")
@limiter.limit("5/hour")
def reset_password(
    request: Request, data: ResetPasswordRequest, db: Session = Depends(get_db)
):
    reset_token = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token == data.token,
            PasswordResetToken.expires_at > datetime.utcnow(),
        )
        .first()
    )

    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    admin = db.query(AdminUser).filter(AdminUser.email == reset_token.email).first()
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Admin user not found"
        )

    admin.hashed_password = auth.get_password_hash(data.new_password)

    db.delete(reset_token)
    db.commit()

    return {"status": "ok", "message": "Password updated successfully"}


@router.post("/admin/trips/notify")
def send_manual_notification(
    data: AdminTripNotificationRequest,
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    session = db.query(TripSession).filter(TripSession.id == data.trip_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Trip session not found")

    if not session.device_token:
        raise HTTPException(
            status_code=400,
            detail="This trip session does not have a device token associated with it",
        )

    notification = TripNotification(
        session_id=session.id, message=data.message, is_read=False
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)

    result = notifier.send_alert(
        device_token=session.device_token,
        trip_id=str(session.id),
        alert_type="ADMIN_MESSAGE",
        message_text=data.message,
        notification_id=notification.id,
    )

    if not result.get("success"):
        return {
            "status": "warning",
            "message": f"Notification saved but FCM failed: {result.get('error')}",
            "notification_id": notification.id,
        }

    return {
        "status": "ok",
        "message": "Notification sent successfully",
        "notification_id": notification.id,
    }
