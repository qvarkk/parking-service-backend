from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from database import get_db
from models.core import UserRequest, TestSnapshot, AdminUser
from schemas.auth import Token
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


# TODO: замена на реальные данные
@router.get("/admin/cameras")
def get_admin_cameras_mock(current_admin: AdminUser = Depends(get_current_admin)):
    return [
        {"id": 1, "lat": 55.75, "lon": 37.61, "status": "ok", "name": "Camera 1"},
        {
            "id": 2,
            "lat": 55.76,
            "lon": 37.62,
            "status": "unreachable",
            "name": "Camera 2",
        },
    ]


# TODO: замена на реальные данные
@router.post("/admin/cameras")
def create_admin_camera_mock(
    data: dict, current_admin: AdminUser = Depends(get_current_admin)
):
    return {"id": 3, "status": "unknown", **data}


# TODO: замена на реальные данные
@router.post("/admin/cameras/{camera_id}/status")
def update_camera_status_mock(
    camera_id: int, data: dict, current_admin: AdminUser = Depends(get_current_admin)
):
    return {
        "status": "ok",
        "camera_id": camera_id,
        "new_status": data.get("status", "ok"),
    }


# TODO: замена на реальные данные
@router.get("/auth/captcha-config")
def get_captcha_config_mock():
    return {"site_key": "mock-site-key-12345", "enabled": True}


# TODO: замена на реальные данные
@router.post("/auth/bootstrap-admin")
def bootstrap_admin_mock(data: dict):
    return {"status": "ok", "message": "Admin bootstrapped (if it was first run)"}


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
