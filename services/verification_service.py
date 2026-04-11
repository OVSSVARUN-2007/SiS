import secrets
from datetime import datetime, timedelta, timezone

from config import get_settings
from services.email_service import send_email

settings = get_settings()


def generate_otp_code() -> str:
    return f"{secrets.randbelow(1000000):06d}"


def create_email_otp(user) -> str:
    otp_code = generate_otp_code()
    now = datetime.now(timezone.utc)
    user.email_verified = 0
    user.email_otp_code = otp_code
    user.email_otp_sent_at = now
    user.email_otp_expires_at = now + timedelta(minutes=settings.otp_expire_minutes)
    return otp_code


def clear_email_otp(user) -> None:
    user.email_verified = 1
    user.email_otp_code = None
    user.email_otp_expires_at = None
    user.email_otp_sent_at = None


def is_otp_valid(user, otp_code: str) -> bool:
    if not user.email_otp_code or not user.email_otp_expires_at:
        return False
    expires_at = user.email_otp_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return user.email_otp_code == otp_code and expires_at >= datetime.now(timezone.utc)


def send_verification_otp(user) -> str:
    otp_code = create_email_otp(user)
    subject = "Verify your SiS account"
    text_body = (
        f"Hello {user.full_name},\n\n"
        f"Your SiS verification code is {otp_code}. "
        f"It expires in {settings.otp_expire_minutes} minutes.\n\n"
        "If you did not request this, please ignore this email."
    )
    html_body = (
        f"<p>Hello {user.full_name},</p>"
        f"<p>Your <strong>SiS verification code</strong> is:</p>"
        f"<p style='font-size:24px;letter-spacing:4px;'><strong>{otp_code}</strong></p>"
        f"<p>This code expires in {settings.otp_expire_minutes} minutes.</p>"
        "<p>If you did not request this, please ignore this email.</p>"
    )
    return send_email(
        to_email=user.email,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
    )
