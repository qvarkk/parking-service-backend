from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from schemas.parking import (
    TripSessionCreate,
    TripSessionResponse,
    NotificationResponse,
    NotificationReadRequest,
)
from models.core import TripSession, TripStatus, TripNotification

router = APIRouter(prefix="/trip-monitoring", tags=["Trip API"])


@router.post("/sessions", response_model=TripSessionResponse)
def create_trip_session(req: TripSessionCreate, db: Session = Depends(get_db)):
    session = TripSession(
        target_lat=req.target_lat,
        target_lon=req.target_lon,
        device_token=req.device_token,
    )
    db.add(session)
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
    # Fallback notifications pull mechanism
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
def cancel_trip_session(session_id: int):
    # Mock data
    return TripSessionResponse(
        id=session_id,
        status=TripStatus.cancelled,
        target_lat=55.75,
        target_lon=37.61
    )


@router.post("/runner/check-due")
def check_due_sessions():
    return {"status": "ok", "checked_sessions": 42, "expired": 3}
