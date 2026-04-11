import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, engine, Base
from models.core import (
    AdminUser,
    TestCamera,
    CameraStatus,
    TripSession,
    TripStatus,
    TripNotification,
)
from services.auth import get_password_hash


def seed_database():
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    if not db.query(AdminUser).filter(AdminUser.email == "admin@example.com").first():
        admin = AdminUser(
            email="admin@example.com",
            hashed_password=get_password_hash("admin123"),
            is_active=True,
        )
        db.add(admin)
        print("[+] Добавлен администратор: admin@example.com / admin123")
    else:
        print("[-] Администратор уже существует.")

    if db.query(TestCamera).count() == 0:
        cameras = [
            TestCamera(name="ЦУМ", lat=55.7601, lon=37.6202, status=CameraStatus.ok),
            TestCamera(
                name="Новый Арбат",
                lat=55.7525,
                lon=37.5983,
                status=CameraStatus.ok,
            ),
            TestCamera(
                name="Тверская",
                lat=55.7650,
                lon=37.6050,
                status=CameraStatus.camera_unreachable,
            ),
            TestCamera(
                name="Парк Горького",
                lat=55.7282,
                lon=37.6011,
                status=CameraStatus.ok,
            ),
        ]
        db.add_all(cameras)
        db.commit()
        print(f"[+] Добавлено {len(cameras)} тестовых камер.")
    else:
        print("[-] Камеры уже существуют.")

    if db.query(TripSession).count() == 0:
        active_camera = (
            db.query(TestCamera).filter(TestCamera.status == CameraStatus.ok).first()
        )
        if active_camera:
            session = TripSession(
                target_camera_id=active_camera.id,
                device_token="1234567890",
                status=TripStatus.active,
            )
            db.add(session)
            db.commit()
            print(
                f"[+] Добавлена активная сессия пользователя к камере id={active_camera.id}."
            )
        else:
            print("[-] Нет активных камер.")
    else:
        print("[-] Сессии поездок уже существуют.")

    db.commit()
    db.close()
    print("Успешно завершено!")


if __name__ == "__main__":
    seed_database()
