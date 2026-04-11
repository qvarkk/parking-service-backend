import logging
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, messaging

from config import settings

logger = logging.getLogger(__name__)

_DEFAULT_KEY_FILE = "serviceAccountKey.json"


class FCMNotifier:

    def __init__(self, credentials_path: Optional[str] = None):
        self.initialized = False
        self.app = None

        filename = (
            credentials_path
            or settings.FIREBASE_CREDENTIALS
            or _DEFAULT_KEY_FILE
        )
        found_path = self._find_credentials_file(filename)

        if not found_path:
            logger.error(
                "FCM: файл ключа не найден (%r). Укажите в .env: "
                "FIREBASE_CREDENTIALS=/абсолютный/путь/serviceAccountKey.json "
                "(файл ключа не храните в репозитории).",
                filename,
            )
            return

        try:
            cred = credentials.Certificate(str(found_path))
            if not firebase_admin._apps:
                self.app = firebase_admin.initialize_app(cred)
            else:
                self.app = firebase_admin.get_app()
            self.initialized = True
            logger.info("FCM инициализирован (%s)", found_path)
        except Exception as e:
            logger.exception("FCM: ошибка инициализации: %s", e)
    
    def _find_credentials_file(self, filename: str) -> Optional[Path]:
        candidates = [
            Path(filename),
            Path.cwd() / filename,
            Path(__file__).resolve().parent.parent / filename,
        ]
        for path in candidates:
            if path.exists() and path.is_file():
                return path.resolve()
        return None
    
    def send_alert(
        self,
        device_token: str,
        trip_id: str,
        alert_type: str,
        message_text: str,
        notification_id: Optional[int] = None,
        free_spots: Optional[int] = None
    ) -> Dict[str, Any]:
        if not self.initialized:
            return {"success": False, "error": "FCM not initialized"}
            
        if not device_token:
            return {"success": False, "error": "Device token is empty"}
        
        title_map = {
            "FEW_SPOTS_LEFT": "Мало мест!",
            "NO_SPOTS": "Мест нет!",
            "SPOTS_AVAILABLE": "Появились места!",
        }

        data_payload = {
            "trip_id": str(trip_id),
            "type": "PARKING_ALERT",
            "alert_type": alert_type,
            "timestamp": datetime.now().isoformat(),
        }
        
        if notification_id is not None:
            data_payload["notification_id"] = str(notification_id)
        
        if free_spots is not None:
            data_payload["free_spots"] = str(free_spots)

        message = messaging.Message(
            notification=messaging.Notification(
                title=title_map.get(alert_type, "Обновление"),
                body=message_text,
            ),
            data=data_payload,
            token=device_token,
        )
        
        try:
            response = messaging.send(message)
            logger.info("FCM alert отправлен type=%s", alert_type)
            return {"success": True, "message_id": response}
        except messaging.UnregisteredError:
            logger.warning("FCM: токен снят с регистрации")
            return {"success": False, "error": "Device token is not registered"}
        except Exception as e:
            logger.error("FCM: %s", e)
            return {"success": False, "error": str(e)}


notifier = FCMNotifier()