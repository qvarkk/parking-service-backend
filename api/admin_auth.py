from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from database import get_db
from models.core import UserRequest, TestSnapshot, AdminUser, TestCamera
from schemas.auth import Token
from schemas.parking import (
    AdminCameraResponse,
    AdminCameraCreate,
    AdminCameraStatusUpdate,
)
from services import auth
from config import settings
from jose import JWTError, jwt

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
        if email is None:
            raise credentials_exception
    except JWTError as exc:
        raise credentials_exception from exc

    admin = db.query(AdminUser).filter(AdminUser.email == email).first()
    if admin is None:
        raise credentials_exception
    return admin


@router.post("/auth/login", response_model=Token)
def login(
    db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()
):
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
    total = db.query(UserRequest).count()
    return {"total_requests": total}


@router.get("/admin/stats/availability")
def get_availability_stats(
    db: Session = Depends(get_db), current_admin: AdminUser = Depends(get_current_admin)
):
    total = db.query(TestSnapshot).count()
    return {"total_snapshots_received": total}


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


# TODO: замена на реальные данные
@router.get("/auth/captcha-config")
def get_captcha_config_mock():
    return {"site_key": "mock-site-key-12345", "enabled": True}


@router.post("/auth/bootstrap-admin")
def bootstrap_admin(db: Session = Depends(get_db)):
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


# TODO: замена на реальные данные
@router.post("/auth/logout")
def logout_mock(current_admin: AdminUser = Depends(get_current_admin)):
    return {"status": "ok"}


# TODO: замена на реальные данные
@router.get("/auth/me")
def get_me_mock(current_admin: AdminUser = Depends(get_current_admin)):
    return {"email": current_admin.email, "is_active": current_admin.is_active}


# TODO: замена на реальные данные
@router.post("/auth/forgot-password")
def forgot_password_mock(data: dict):
    return {"status": "ok", "message": "Reset link sent"}


# TODO: замена на реальные данные
@router.post("/auth/reset-password")
def reset_password_mock(data: dict):
    return {"status": "ok", "message": "Password updated"}
