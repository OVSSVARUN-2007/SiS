from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from database import get_db
from models import StudentRegister
from services.verification_service import clear_email_otp, is_otp_valid, send_verification_otp
from utils.jwt import create_access_token, create_refresh_token, decode_token
from utils.security import verify_password

router = APIRouter(prefix="/api/v2", tags=["api-v2"])
bearer_scheme = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    role: str | None = None


class OtpRequest(BaseModel):
    email: EmailStr


class VerifyOtpRequest(BaseModel):
    email: EmailStr
    otp: str


class UserResponse(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    role: str | None = None
    department: str | None = None
    academic_year: int | None = None
    section: str | None = None


def _unauthorized(detail: str = "Invalid or missing authentication token") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def get_current_api_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> StudentRegister:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise _unauthorized()

    try:
        payload = decode_token(credentials.credentials)
    except Exception as exc:
        raise _unauthorized("Token validation failed") from exc

    if payload.get("type") != "access":
        raise _unauthorized("Access token required")

    user_id = payload.get("sub")
    if not user_id:
        raise _unauthorized()

    user = db.query(StudentRegister).filter(StudentRegister.id == int(user_id)).first()
    if not user:
        raise _unauthorized("User not found")
    return user


def require_role(*roles: str):
    def dependency(user: StudentRegister = Depends(get_current_api_user)) -> StudentRegister:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' is not allowed for this endpoint.",
            )
        return user

    return dependency


def _build_token_response(user: StudentRegister) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(str(user.id), user.role or "student"),
        refresh_token=create_refresh_token(str(user.id), user.role or "student"),
        role=user.role,
    )


@router.post("/auth/login", response_model=TokenResponse)
def api_login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(StudentRegister).filter(StudentRegister.email == payload.email.lower()).first()
    if not user or not verify_password(payload.password, user.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.email_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Email verification required")
    return _build_token_response(user)


@router.post("/auth/refresh", response_model=TokenResponse)
def refresh_access_token(payload: RefreshRequest, db: Session = Depends(get_db)):
    try:
        token_payload = decode_token(payload.refresh_token)
    except Exception as exc:
        raise _unauthorized("Refresh token validation failed") from exc

    if token_payload.get("type") != "refresh":
        raise _unauthorized("Refresh token required")

    user_id = token_payload.get("sub")
    user = db.query(StudentRegister).filter(StudentRegister.id == int(user_id)).first() if user_id else None
    if not user:
        raise _unauthorized("User not found")
    return _build_token_response(user)


@router.post("/auth/logout")
def api_logout():
    return {"message": "Logged out. Discard the access and refresh tokens on the client."}


@router.post("/auth/resend-otp")
def api_resend_otp(payload: OtpRequest, db: Session = Depends(get_db)):
    user = db.query(StudentRegister).filter(StudentRegister.email == payload.email.lower()).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    delivery_mode = send_verification_otp(user)
    db.commit()
    return {"message": "OTP sent", "delivery_mode": delivery_mode}


@router.post("/auth/verify-email")
def api_verify_email(payload: VerifyOtpRequest, db: Session = Depends(get_db)):
    user = db.query(StudentRegister).filter(StudentRegister.email == payload.email.lower()).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    if not is_otp_valid(user, payload.otp.strip()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP")
    clear_email_otp(user)
    db.commit()
    return {"message": "Email verified successfully"}


@router.get("/auth/me", response_model=UserResponse)
def api_me(user: StudentRegister = Depends(get_current_api_user)):
    return UserResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        department=user.department,
        academic_year=user.academic_year,
        section=user.section,
    )


@router.get("/student/profile", response_model=UserResponse)
def student_profile(user: StudentRegister = Depends(require_role("student"))):
    return UserResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        department=user.department,
        academic_year=user.academic_year,
        section=user.section,
    )


@router.get("/admin/profile", response_model=UserResponse)
def admin_profile(user: StudentRegister = Depends(require_role("admin"))):
    return UserResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        department=user.department,
        academic_year=user.academic_year,
        section=user.section,
    )
