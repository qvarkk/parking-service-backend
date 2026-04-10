import asyncio
import logging
import random
from sqlalchemy.orm import Session
from database import SessionLocal
from models.core import TripSession, TripStatus, TripNotification

logger = logging.getLogger(__name__)


async def background_scheduler():
    logger.info("Scheduler started")
    while True:
        try:
            db: Session = SessionLocal()

            active_sessions = (
                db.query(TripSession)
                .filter(TripSession.status == TripStatus.active)
                .all()
            )

            for session in active_sessions:
                if random.random() > 0.8:
                    notification = TripNotification(
                        session_id=session.id,
                        message="Ситуация с парковками в районе изменилась.",
                    )
                    db.add(notification)

                    if session.device_token:
                        logger.info(
                            "FCM Push to %s: %s",
                            session.device_token,
                            notification.message,
                        )

            db.commit()
            db.close()

        except Exception as e:
            logger.error("Scheduler error: %s", e)

        await asyncio.sleep(15)
