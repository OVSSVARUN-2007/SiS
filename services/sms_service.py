import logging

logger = logging.getLogger(__name__)


def send_phone_message(*, to_phone: str, text_body: str) -> str:
    logger.warning(
        "SMS provider not configured. Message to %s was not sent.\n%s",
        to_phone,
        text_body,
    )
    return "console"
