import sys
import os
import random
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import SessionLocal, engine, Base
from models.core import (
    AdminUser,
    TestCamera,
    CameraStatus,
    TripSession,
    TripStatus,
    TripNotification,
    TestSnapshot,
    UserRequest,
)
from services.auth import get_password_hash


def seed_database():
    Base.metadata.drop_all(bind=engine)
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

    print("[*] Проверка снимков камер...")
    cameras = db.query(TestCamera).all()
    for camera in cameras:
        snapshot_count = (
            db.query(TestSnapshot).filter(TestSnapshot.camera_id == camera.id).count()
        )
        if snapshot_count < 5:
            num_to_add = random.randint(5, 10)
            print(
                f"    - Добавление {num_to_add} снимков для камеры {camera.name} (id={camera.id})"
            )
            for _ in range(num_to_add):
                minutes_back = random.randint(0, 10 * 60)
                created_at = datetime.now() - timedelta(minutes=minutes_back)

                snapshot = TestSnapshot(
                    camera_id=camera.id,
                    free_spots_count=random.randint(0, 20),
                    created_at=created_at,
                )
                db.add(snapshot)
    db.commit()

    print("[*] Проверка запросов пользователей...")
    request_count = db.query(UserRequest).count()
    if request_count < 20:
        num_to_add = random.randint(60, 100)
        print(f"    - Добавление {num_to_add} фейковых запросов пользователей")

        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/94.0.4606.81 Safari/537.36"

        for _ in range(num_to_add):
            minutes_back = random.randint(0, 12 * 60)
            created_at = datetime.now() - timedelta(minutes=minutes_back)

            camera = random.choice(cameras) if random.random() > 0.5 else None

            if camera:
                mock_url = f"http://localhost:8000/parking/search"
            else:
                mock_url = f"http://localhost:8000/trip-monitoring/sessions"

            request = UserRequest(
                camera_id=camera.id if camera else None,
                query_address=mock_url,
                lat=camera.lat if camera else 0,
                lon=camera.lon if camera else 0,
                ip_address=f"192.168.1.{random.randint(1, 255)}",
                user_agent=user_agent,
                is_success=random.random() > 0.1,
                created_at=created_at,
            )
            db.add(request)
    db.commit()

    db.close()
    print("Успешно завершено!")


if __name__ == "__main__":
    seed_database()
