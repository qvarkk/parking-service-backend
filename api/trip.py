import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from database import get_db
from schemas.parking import (
    TripSessionCreate,
    TripSessionResponse,
    NotificationResponse,
    NotificationReadRequest,
)
from models.core import (
    UserRequest,
    TripSession,
    TripStatus,
    TripNotification,
    TestCamera,
)
from config import settings
from services import smartcaptcha
from api.utils import get_client_ip

router = APIRouter(prefix="/trip-monitoring", tags=["Trip API"])


@router.post("/sessions", response_model=TripSessionResponse)
def create_trip_session(
    req: TripSessionCreate, request: Request, db: Session = Depends(get_db)
):
    ip = get_client_ip(request)
    ua = request.headers.get("user-agent")
    user_req = UserRequest(
        camera_id=req.target_camera_id, ip_address=ip, user_agent=ua, is_success=False
    )
    db.add(user_req)
    db.commit()

    try:
        smartcaptcha.require_valid_captcha(req.captcha_token, ip)
    except HTTPException as e:
        user_req.error_code = "captcha_invalid"
        db.commit()
        raise e

    camera = db.query(TestCamera).filter(TestCamera.id == req.target_camera_id).first()
    if not camera:
        user_req.error_code = "camera_not_found"
        db.commit()
        raise HTTPException(status_code=404, detail="Target camera not found")

    session = TripSession(
        target_camera_id=req.target_camera_id,
        device_token=req.device_token,
    )
    db.add(session)

    user_req.is_success = True

    db.commit()
    db.refresh(session)
    return session


@router.get("/sessions/{session_id}", response_model=TripSessionResponse)
def get_trip_session(session_id: int, db: Session = Depends(get_db)):
    session = db.query(TripSession).filter(TripSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.get("/notifications/pull", response_model=list[NotificationResponse])
def pull_notifications(session_id: int, db: Session = Depends(get_db)):
    notifications = (
        db.query(TripNotification)
        .filter(
            TripNotification.session_id == session_id, TripNotification.is_read == False
        )
        .all()
    )
    return notifications


@router.post("/notifications/read")
def read_notifications(req: NotificationReadRequest, db: Session = Depends(get_db)):
    db.query(TripNotification).filter(
        TripNotification.id.in_(req.notification_ids)
    ).update({TripNotification.is_read: True})
    db.commit()
    return {"status": "ok"}


@router.post("/sessions/{session_id}/cancel", response_model=TripSessionResponse)
def cancel_trip_session(session_id: int, db: Session = Depends(get_db)):
    session = db.query(TripSession).filter(TripSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.status = TripStatus.cancelled
    db.commit()
    db.refresh(session)
    return session


@router.post("/runner/check-due")
def check_due_sessions(db: Session = Depends(get_db)):
    active_sessions = (
        db.query(TripSession).filter(TripSession.status == TripStatus.active).all()
    )
    checked_count = len(active_sessions)
    expired_count = 0
    now = datetime.datetime.utcnow()

    for session in active_sessions:
        if session.created_at:
            created_utc = session.created_at.replace(tzinfo=None)
            if (
                now - created_utc
            ).total_seconds() > settings.TRIP_EXPIRATION_MINUTES * 60:
                session.status = TripStatus.expired
                expired_count += 1

    if expired_count > 0:
        db.commit()

    return {"status": "ok", "checked_sessions": checked_count, "expired": expired_count}
