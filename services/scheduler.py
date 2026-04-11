import asyncio
import logging
from sqlalchemy.orm import Session
from database import SessionLocal
from models.core import TripSession, TripStatus, TripNotification, TestSnapshot
from services.notification import notifier
from config import settings

logger = logging.getLogger(__name__)

_last_notified_spots = {}


async def background_scheduler():
    logger.info(
        "Scheduler started with interval %s seconds",
        settings.SCHEDULER_INTERVAL_SECONDS,
    )

    while True:
        try:
            db: Session = SessionLocal()

            active_sessions = (
                db.query(TripSession)
                .filter(TripSession.status == TripStatus.active)
                .all()
            )

            active_ids = {s.id for s in active_sessions}
            keys_to_remove = [
                sid for sid in _last_notified_spots if sid not in active_ids
            ]
            for sid in keys_to_remove:
                del _last_notified_spots[sid]

            for session in active_sessions:
                latest_snapshot = (
                    db.query(TestSnapshot)
                    .filter(TestSnapshot.camera_id == session.target_camera_id)
                    .order_by(TestSnapshot.created_at.desc())
                    .first()
                )

                if not latest_snapshot:
                    continue

                new_count = latest_snapshot.free_spots_count

                if session.id not in _last_notified_spots:
                    _last_notified_spots[session.id] = new_count
                    logger.info(
                        "Session %s: baseline set to %s spots", session.id, new_count
                    )
                    continue

                old_count = _last_notified_spots[session.id]

                message = None
                alert_type = None

                if new_count == 0 and old_count > 0:
                    message = "Места закончились!"
                    alert_type = "NO_SPOTS"
                else:
                    diff = abs(new_count - old_count)
                    threshold = settings.PARKING_THRESHOLD_PERCENT

                    if (diff / max(old_count, 1)) >= (threshold / 100.0):
                        if new_count < old_count:
                            message = f"Места заканчиваются! Осталось {new_count}."
                            alert_type = "FEW_SPOTS_LEFT"
                        else:
                            message = (
                                f"Появилось еще больше мест! Теперь их {new_count}."
                            )
                            alert_type = "SPOTS_AVAILABLE"

                if message and alert_type:
                    logger.info(
                        "Session %s: notifying %s (%s -> %s)",
                        session.id,
                        alert_type,
                        old_count,
                        new_count,
                    )

                    notification = TripNotification(
                        session_id=session.id,
                        message=message,
                    )
                    db.add(notification)
                    db.flush()

                    if session.device_token:
                        notifier.send_alert(
                            device_token=session.device_token,
                            trip_id=str(session.id),
                            alert_type=alert_type,
                            message_text=message,
                            notification_id=notification.id,
                            free_spots=new_count,
                        )

                    _last_notified_spots[session.id] = new_count

            db.commit()
            db.close()

        except Exception as e:
            logger.exception("Scheduler error: %s", e)

        await asyncio.sleep(settings.SCHEDULER_INTERVAL_SECONDS)
