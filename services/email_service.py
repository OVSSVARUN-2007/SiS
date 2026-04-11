import logging
import smtplib
from email.message import EmailMessage

from config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


def send_email(*, to_email: str, subject: str, html_body: str, text_body: str) -> str:
    if not settings.smtp_host or not settings.smtp_from_email:
        logger.warning("SMTP not configured. Email to %s was not sent.\nSubject: %s\n%s", to_email, subject, text_body)
        return "console"

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    message["To"] = to_email
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)
    return "email"
