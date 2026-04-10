import hashlib
import hmac
import os


def hash_password(password: str, iterations: int = 120000) -> str:
    salt = os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    ).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def verify_password(plain_password: str, stored_password: str) -> bool:
    if not stored_password:
        return False

    if stored_password.startswith("pbkdf2_sha256$"):
        try:
            _, iter_str, salt, digest = stored_password.split("$", 3)
            check = hashlib.pbkdf2_hmac(
                "sha256",
                plain_password.encode("utf-8"),
                salt.encode("utf-8"),
                int(iter_str),
            ).hex()
            return hmac.compare_digest(check, digest)
        except Exception:
            return False

    # Legacy fallback: plain text passwords in existing data.
    return hmac.compare_digest(plain_password, stored_password)
