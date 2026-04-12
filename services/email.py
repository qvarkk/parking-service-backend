import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from config import settings

logger = logging.getLogger(__name__)


def send_reset_password_email(email_to: str, token: str):
    subject = f"Восстановление пароля для {settings.PROJECT_NAME}"
    link = f"{settings.FRONTEND_URL}/reset-password?token={token}"

    html_content = f"""
    <html>
        <body>
            <p>Вы получили это письмо, потому что запросили сброс пароля для своей учетной записи.</p>
            <p>Пожалуйста, перейдите по следующей ссылке, чтобы сбросить пароль:</p>
            <p><a href="{link}">{link}</a></p>
            <p>Если вы не запрашивали сброс пароля, просто проигнорируйте это письмо.</p>
        </body>
    </html>
    """

    if not settings.SMTP_HOST:
        logger.warning(
            "SMTP_HOST not configured. Logging reset link instead of sending email."
        )
        logger.info(f"RESET LINK for {email_to}: {link}")
        return

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>"
    message["To"] = email_to

    part = MIMEText(html_content, "html")
    message.attach(part)

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            if settings.SMTP_TLS:
                server.starttls()
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.EMAILS_FROM_EMAIL, email_to, message.as_string())
        logger.info(f"Reset email sent to {email_to}")
    except Exception as e:
        logger.error(f"Failed to send reset email to {email_to}: {e}")
        logger.info(f"RESET LINK FOR {email_to}: {link}")
