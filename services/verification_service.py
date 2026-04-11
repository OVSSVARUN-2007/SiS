import secrets
from datetime import datetime, timedelta, timezone

from config import get_settings
from services.email_service import send_email
from services.sms_service import send_phone_message

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


def create_password_reset_otp(user) -> str:
    otp_code = generate_otp_code()
    now = datetime.now(timezone.utc)
    user.email_otp_code = otp_code
    user.email_otp_sent_at = now
    user.email_otp_expires_at = now + timedelta(minutes=settings.otp_expire_minutes)
    return otp_code


def clear_password_reset_otp(user) -> None:
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


def mask_contact(value: str, *, is_email: bool) -> str:
    if is_email:
        local_part, _, domain = value.partition("@")
        if len(local_part) <= 2:
            local_mask = local_part[0] + "*" if local_part else "***"
        else:
            local_mask = local_part[:2] + "*" * max(len(local_part) - 2, 1)
        return f"{local_mask}@{domain}" if domain else local_mask
    if len(value) <= 4:
        return "*" * len(value)
    return "*" * (len(value) - 4) + value[-4:]


def send_password_reset_otp(user, contact: str) -> dict[str, str]:
    otp_code = create_password_reset_otp(user)
    is_email = "@" in contact
    masked_contact = mask_contact(contact, is_email=is_email)
    message = (
        f"Hello {user.full_name},\n\n"
        f"Your SiS password reset OTP is {otp_code}. "
        f"It expires in {settings.otp_expire_minutes} minutes.\n\n"
        "If you did not request this, please ignore this message."
    )

    if is_email:
        subject = "Reset your SiS password"
        html_body = (
            f"<p>Hello {user.full_name},</p>"
            f"<p>Your <strong>SiS password reset OTP</strong> is:</p>"
            f"<p style='font-size:24px;letter-spacing:4px;'><strong>{otp_code}</strong></p>"
            f"<p>This code expires in {settings.otp_expire_minutes} minutes.</p>"
            "<p>If you did not request this, please ignore this message.</p>"
        )
        delivery_mode = send_email(
            to_email=contact,
            subject=subject,
            html_body=html_body,
            text_body=message,
        )
        channel = "email"
    else:
        delivery_mode = send_phone_message(to_phone=contact, text_body=message)
        channel = "phone"

    return {
        "channel": channel,
        "delivery_mode": delivery_mode,
        "destination": masked_contact,
    }
