import logging
from typing import Optional

import httpx

from config import settings

logger = logging.getLogger(__name__)

_VALIDATE_URL = "https://smartcaptcha.cloud.yandex.ru/validate"


def is_enabled() -> bool:
    return bool(settings.SMARTCAPTCHA_SERVER_KEY and settings.SMARTCAPTCHA_SERVER_KEY.strip())


def verify_token(token: str, remote_ip: Optional[str]) -> bool:
    secret = (settings.SMARTCAPTCHA_SERVER_KEY or "").strip()
    if not secret:
        return True

    data = {"secret": secret, "token": token, "ip": (remote_ip or "").strip()}

    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(_VALIDATE_URL, data=data)
    except httpx.RequestError as exc:
        logger.warning("SmartCaptcha: запрос не выполнен: %s", exc)
        return True

    if resp.status_code != 200:
        logger.warning("SmartCaptcha: HTTP %s", resp.status_code)
        return True

    try:
        body = resp.json()
    except ValueError:
        logger.warning("SmartCaptcha: ответ не JSON")
        return True

    ok = body.get("status") == "ok"
    if not ok:
        logger.info("SmartCaptcha: status=%s", body.get("status"))
    return ok


def require_valid_captcha(token: Optional[str], remote_ip: Optional[str]) -> None:
    from fastapi import HTTPException

    if not is_enabled():
        return
    if not token or not str(token).strip():
        raise HTTPException(status_code=400, detail="captcha_token is required")
    if not verify_token(str(token).strip(), remote_ip):
        raise HTTPException(status_code=400, detail="SmartCaptcha verification failed")
