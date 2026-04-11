from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
from sqlalchemy.orm import Session
from datetime import datetime

from database import get_db
from models import (
    Assignment,
    Attendance,
    Enrollment,
    StudentRequest,
    Submission,
    Student,
    StudentRegister,
)
from services.verification_service import clear_password_reset_otp, is_otp_valid, mask_contact, send_password_reset_otp
from services.dashboard_service import build_student_dashboard_context
from utils.form_data import safe_form_to_dict
from utils.security import hash_password, verify_password

router = APIRouter()
templates = Jinja2Templates(directory="templates")
RESET_USER_SESSION_KEY = "password_reset_user_id"
RESET_ALLOWED_SESSION_KEY = "password_reset_allowed"
RESET_CONTACT_SESSION_KEY = "password_reset_contact"


def normalize_login_identifier(value: str) -> str:
    candidate = value.strip()
    return candidate.lower() if "@" in candidate else candidate


def find_user_by_identifier(db: Session, identifier: str) -> StudentRegister | None:
    normalized = normalize_login_identifier(identifier)
    return (
        db.query(StudentRegister)
        .filter(or_(StudentRegister.email == normalized, StudentRegister.phone == normalized))
        .first()
    )


def clear_password_reset_session(request: Request) -> None:
    request.session.pop(RESET_USER_SESSION_KEY, None)
    request.session.pop(RESET_ALLOWED_SESSION_KEY, None)
    request.session.pop(RESET_CONTACT_SESSION_KEY, None)


def get_current_user(request: Request, db: Session) -> StudentRegister | None:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.query(StudentRegister).filter(StudentRegister.id == user_id).first()


@router.get("/signup")
def signup_page(request: Request):
    return templates.TemplateResponse(request, "signup.html", {"request": request, "error": None, "message": None})


@router.post("/signup")
async def signup(
    request: Request,
    db: Session = Depends(get_db),
):
    form = await safe_form_to_dict(request)
    full_name = (form.get("full_name") or "").strip()
    email = (form.get("email") or "").strip().lower()
    password = form.get("password") or ""
    phone = (form.get("phone") or "").strip() or None
    gender = (form.get("gender") or "").strip() or None
    date_of_birth = (form.get("date_of_birth") or "").strip() or None
    department = (form.get("department") or "").strip() or None
    academic_year_raw = (form.get("academic_year") or "").strip()
    section = (form.get("section") or "").strip() or None

    if not full_name or not email or not password:
        return templates.TemplateResponse(
            request,
            "signup.html",
            {"request": request, "error": "Name, email and password are required."},
            status_code=400,
        )

    existing = db.query(StudentRegister).filter(StudentRegister.email == email).first()
    if existing:
        return templates.TemplateResponse(
            request,
            "signup.html",
            {"request": request, "error": "Email is already registered."},
            status_code=400,
        )

    hashed_password = hash_password(password)
    dob_value = None
    academic_year = None
    if date_of_birth:
        try:
            dob_value = datetime.strptime(date_of_birth, "%Y-%m-%d").date()
        except ValueError:
            return templates.TemplateResponse(
                request,
                "signup.html",
                {"request": request, "error": "Invalid date of birth format."},
                status_code=400,
            )
    if academic_year_raw.isdigit():
        academic_year = int(academic_year_raw)

    user = StudentRegister(
        full_name=full_name,
        email=email,
        password=hashed_password,
        phone=phone or None,
        gender=gender or None,
        date_of_birth=dob_value,
        department=department,
        academic_year=academic_year,
        section=section,
        role="student",
        is_active=1,
        email_verified=1,
    )
    db.add(user)
    db.flush()

    # Keep legacy students table synced for compatibility with existing modules.
    db.add(Student(name=full_name, email=email, password=hashed_password, role="student"))
    db.commit()

    return templates.TemplateResponse(
        request,
        "login.html",
        {"request": request, "error": None, "message": "Account created successfully. You can log in now."},
        status_code=201,
    )


@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"request": request, "error": None, "message": None})


@router.post("/login")
async def login(
    request: Request,
    db: Session = Depends(get_db),
):
    form = await safe_form_to_dict(request)
    email = (form.get("email") or "").strip().lower()
    password = form.get("password") or ""

    user = db.query(StudentRegister).filter(StudentRegister.email == email).first()
    if not user or not verify_password(password, user.password):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"request": request, "error": "Invalid email or password.", "message": None},
            status_code=401,
        )
    request.session["user_id"] = user.id
    request.session["user_name"] = user.full_name
    request.session["role"] = user.role
    if user.role == "admin":
        return RedirectResponse(url="/admin/dashboard", status_code=303)
    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


@router.get("/forgot-password")
def forgot_password_page(request: Request):
    clear_password_reset_session(request)
    return templates.TemplateResponse(
        request,
        "forgot_password.html",
        {"request": request, "error": None, "message": None},
    )


@router.post("/forgot-password")
async def forgot_password(request: Request, db: Session = Depends(get_db)):
    form = await safe_form_to_dict(request)
    identifier = normalize_login_identifier(form.get("identifier") or "")
    user = find_user_by_identifier(db, identifier)

    if not identifier:
        return templates.TemplateResponse(
            request,
            "forgot_password.html",
            {"request": request, "error": "Enter your email or phone number.", "message": None},
            status_code=400,
        )
    if not user:
        return templates.TemplateResponse(
            request,
            "forgot_password.html",
            {"request": request, "error": "No account found for that email or phone number.", "message": None},
            status_code=404,
        )

    delivery = send_password_reset_otp(user, identifier)
    db.commit()
    request.session[RESET_USER_SESSION_KEY] = user.id
    request.session[RESET_CONTACT_SESSION_KEY] = identifier
    request.session[RESET_ALLOWED_SESSION_KEY] = False

    return templates.TemplateResponse(
        request,
        "forgot_password_verify.html",
        {
            "request": request,
            "error": None,
            "message": f"OTP sent to your {delivery['channel']} {delivery['destination']}.",
            "delivery_mode": delivery["delivery_mode"],
            "channel": delivery["channel"],
            "destination": delivery["destination"],
        },
    )


@router.get("/forgot-password/verify")
def forgot_password_verify_page(request: Request):
    if not request.session.get(RESET_USER_SESSION_KEY):
        return RedirectResponse(url="/forgot-password", status_code=303)
    contact = request.session.get(RESET_CONTACT_SESSION_KEY) or ""
    channel = "email" if "@" in contact else "phone"
    return templates.TemplateResponse(
        request,
        "forgot_password_verify.html",
        {
            "request": request,
            "error": None,
            "message": None,
            "delivery_mode": None,
            "channel": channel,
            "destination": mask_contact(contact, is_email=channel == "email"),
        },
    )


@router.post("/forgot-password/resend-otp")
async def resend_password_reset_otp(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get(RESET_USER_SESSION_KEY)
    contact = request.session.get(RESET_CONTACT_SESSION_KEY)
    if not user_id or not contact:
        return RedirectResponse(url="/forgot-password", status_code=303)

    user = db.query(StudentRegister).filter(StudentRegister.id == user_id).first()
    if not user:
        clear_password_reset_session(request)
        return RedirectResponse(url="/forgot-password", status_code=303)

    delivery = send_password_reset_otp(user, contact)
    db.commit()

    return templates.TemplateResponse(
        request,
        "forgot_password_verify.html",
        {
            "request": request,
            "error": None,
            "message": f"A new OTP has been sent to your {delivery['channel']} {delivery['destination']}.",
            "delivery_mode": delivery["delivery_mode"],
            "channel": delivery["channel"],
            "destination": delivery["destination"],
        },
    )


@router.post("/forgot-password/verify")
async def forgot_password_verify(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get(RESET_USER_SESSION_KEY)
    contact = request.session.get(RESET_CONTACT_SESSION_KEY)
    if not user_id or not contact:
        return RedirectResponse(url="/forgot-password", status_code=303)

    user = db.query(StudentRegister).filter(StudentRegister.id == user_id).first()
    if not user:
        clear_password_reset_session(request)
        return RedirectResponse(url="/forgot-password", status_code=303)

    form = await safe_form_to_dict(request)
    otp = (form.get("otp") or "").strip()
    if not is_otp_valid(user, otp):
        channel = "email" if "@" in contact else "phone"
        return templates.TemplateResponse(
            request,
            "forgot_password_verify.html",
            {
                "request": request,
                "error": "Invalid or expired OTP. Please try again.",
                "message": None,
                "delivery_mode": None,
                "channel": channel,
                "destination": mask_contact(contact, is_email=channel == "email"),
            },
            status_code=400,
        )

    clear_password_reset_otp(user)
    db.commit()
    request.session[RESET_ALLOWED_SESSION_KEY] = True
    return RedirectResponse(url="/reset-password", status_code=303)


@router.get("/reset-password")
def reset_password_page(request: Request):
    if not request.session.get(RESET_USER_SESSION_KEY) or not request.session.get(RESET_ALLOWED_SESSION_KEY):
        return RedirectResponse(url="/forgot-password", status_code=303)
    return templates.TemplateResponse(
        request,
        "reset_password.html",
        {"request": request, "error": None, "message": None},
    )


@router.post("/reset-password")
async def reset_password(request: Request, db: Session = Depends(get_db)):
    user_id = request.session.get(RESET_USER_SESSION_KEY)
    if not user_id or not request.session.get(RESET_ALLOWED_SESSION_KEY):
        return RedirectResponse(url="/forgot-password", status_code=303)

    user = db.query(StudentRegister).filter(StudentRegister.id == user_id).first()
    if not user:
        clear_password_reset_session(request)
        return RedirectResponse(url="/forgot-password", status_code=303)

    form = await safe_form_to_dict(request)
    password = form.get("password") or ""
    confirm_password = form.get("confirm_password") or ""
    if not password or not confirm_password:
        return templates.TemplateResponse(
            request,
            "reset_password.html",
            {"request": request, "error": "Enter and confirm your new password.", "message": None},
            status_code=400,
        )
    if password != confirm_password:
        return templates.TemplateResponse(
            request,
            "reset_password.html",
            {"request": request, "error": "Passwords do not match.", "message": None},
            status_code=400,
        )

    hashed_password = hash_password(password)
    user.password = hashed_password
    legacy_user = db.query(Student).filter(Student.email == user.email).first()
    if legacy_user:
        legacy_user.password = hashed_password
    db.commit()
    clear_password_reset_session(request)

    template_name = "admin_login.html" if user.role == "admin" else "login.html"
    return templates.TemplateResponse(
        request,
        template_name,
        {"request": request, "error": None, "message": "Password reset successful. You can log in now."},
    )


@router.get("/dashboard")
def dashboard(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if user.role == "admin":
        return RedirectResponse(url="/admin/dashboard", status_code=303)

    context = build_student_dashboard_context(db, user)

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "request": request,
            **context,
        },
    )


@router.post("/requests")
async def create_request(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if user.role == "admin":
        return RedirectResponse(url="/admin/dashboard", status_code=303)

    form = await safe_form_to_dict(request)
    category = (form.get("category") or "").strip().lower()
    title = (form.get("title") or "").strip()
    description = (form.get("description") or "").strip()
    proof_url = (form.get("proof_url") or "").strip() or None

    if category not in {"bonafide", "leave", "certificate"} or not title or not description:
        context = build_student_dashboard_context(db, user)
        return templates.TemplateResponse(
            request,
            "index.html",
            {
                "request": request,
                **context,
                "request_error": "Category, title, and description are required.",
            },
            status_code=400,
        )

    db.add(
        StudentRequest(
            student_id=user.id,
            category=category,
            title=title,
            description=description,
            proof_url=proof_url,
            status="pending",
        )
    )
    db.commit()
    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/attendance")
def attendance_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if user.role == "admin":
        return RedirectResponse(url="/admin/dashboard", status_code=303)

    records = (
        db.query(Attendance)
        .filter(Attendance.student_id == user.id)
        .order_by(Attendance.date.desc())
        .all()
    )

    present_count = len([record for record in records if record.status == "present"])
    absent_count = len([record for record in records if record.status == "absent"])
    total = len(records)
    percentage = round((present_count / total) * 100, 2) if total else 0

    return templates.TemplateResponse(
        request,
        "Attendance.html",
        {
            "request": request,
            "user": user,
            "records": records,
            "present_count": present_count,
            "absent_count": absent_count,
            "percentage": percentage,
        },
    )


@router.post("/assignments/{assignment_id}/submit")
async def submit_assignment(
    assignment_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if user.role == "admin":
        return RedirectResponse(url="/admin/dashboard", status_code=303)

    assignment = db.query(Assignment).filter(Assignment.id == assignment_id).first()
    if not assignment:
        return RedirectResponse(url="/dashboard", status_code=303)

    enrolled_course_ids = {
        row.course_id
        for row in db.query(Enrollment).filter(Enrollment.student_id == user.id).all()
        if row.course_id
    }
    class_match = True
    if assignment.department and assignment.department != user.department:
        class_match = False
    if assignment.academic_year and assignment.academic_year != user.academic_year:
        class_match = False
    if assignment.section and assignment.section != user.section:
        class_match = False

    if not (assignment.course_id in enrolled_course_ids or class_match):
        return RedirectResponse(url="/dashboard", status_code=303)

    form = await safe_form_to_dict(request)
    content = (form.get("content") or "").strip()

    existing_submission = (
        db.query(Submission)
        .filter(
            Submission.assignment_id == assignment_id,
            Submission.student_id == user.id,
        )
        .first()
    )
    if existing_submission:
        return RedirectResponse(url="/dashboard", status_code=303)

    db.add(
        Submission(
            assignment_id=assignment_id,
            student_id=user.id,
            content=content or "Submitted",
        )
    )
    db.commit()
    return RedirectResponse(url="/dashboard", status_code=303)
