import asyncio
import logging
import random
from pathlib import Path
from sqlalchemy.orm import Session
from database import SessionLocal
from models.core import (
    TripSession,
    TripStatus,
    TripNotification,
    TestSnapshot,
    TestCamera,
)
from services.notification import notifier
from services.parking_inference import count_parking_spots_from_image
from config import settings

logger = logging.getLogger(__name__)

_last_notified_spots = {}


async def image_ingestion_scheduler():
    """
    Периодическая загрузка случайных фото для всех камер.
    """
    logger.info(
        "Image Ingestion Scheduler started with interval %s seconds",
        settings.SCHEDULER_IMAGE_INTERVAL_SECONDS,
    )

    while True:
        try:
            db: Session = SessionLocal()
            cameras = db.query(TestCamera).all()

            for camera in cameras:
                n = random.randint(1, 3)
                image_name = f"cam_{camera.id}_{n}.jpg"
                image_path = Path("cam-images") / image_name

                if image_path.is_file():
                    try:
                        logger.info(
                            "AI Processing for camera %s using %s",
                            camera.id,
                            image_name,
                        )
                        ai_result = count_parking_spots_from_image(image_path)

                        new_snapshot = TestSnapshot(
                            camera_id=camera.id,
                            image_url=str(image_path),
                            free_spots_count=ai_result.free_spots,
                        )
                        db.add(new_snapshot)
                    except Exception as ai_err:
                        logger.error(
                            "AI inference failed for camera %s: %s", camera.id, ai_err
                        )
                else:
                    logger.debug("File %s not found in cam-images/", image_path)

            db.commit()
            db.close()

        except Exception as e:
            logger.exception("Image Ingestion Error: %s", e)

        await asyncio.sleep(settings.SCHEDULER_IMAGE_INTERVAL_SECONDS)


async def background_scheduler():
    """
    Периодический мониторинг активных сессий и отправка уведомлений.
    """
    logger.info(
        "Notification Scheduler started with interval %s seconds",
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
                        "Session %s (Cam %s): baseline set to %s spots",
                        session.id,
                        session.target_camera_id,
                        new_count,
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
            logger.exception("Notification Scheduler error: %s", e)

        await asyncio.sleep(settings.SCHEDULER_INTERVAL_SECONDS)
