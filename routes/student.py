from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
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
from services.verification_service import clear_email_otp, is_otp_valid, send_verification_otp
from services.dashboard_service import build_student_dashboard_context
from utils.form_data import safe_form_to_dict
from utils.security import hash_password, verify_password

router = APIRouter()
templates = Jinja2Templates(directory="templates")


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
        email_verified=0,
    )
    db.add(user)
    db.flush()

    # Keep legacy students table synced for compatibility with existing modules.
    db.add(Student(name=full_name, email=email, password=hashed_password, role="student"))
    delivery_mode = send_verification_otp(user)
    db.commit()

    return templates.TemplateResponse(
        request,
        "verify_email.html",
        {
            "request": request,
            "email": email,
            "error": None,
            "message": "Account created. Please verify your email to continue.",
            "delivery_mode": delivery_mode,
        },
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
    if not user.email_verified:
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "request": request,
                "error": "Please verify your email before logging in.",
                "message": f"Use the OTP sent to {user.email} or request a new one.",
            },
            status_code=403,
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


@router.get("/verify-email")
def verify_email_page(request: Request):
    email = (request.query_params.get("email") or "").strip().lower()
    return templates.TemplateResponse(
        request,
        "verify_email.html",
        {"request": request, "email": email, "error": None, "message": None, "delivery_mode": None},
    )


@router.post("/verify-email")
async def verify_email(request: Request, db: Session = Depends(get_db)):
    form = await safe_form_to_dict(request)
    email = (form.get("email") or "").strip().lower()
    otp = (form.get("otp") or "").strip()
    user = db.query(StudentRegister).filter(StudentRegister.email == email).first()

    if not user:
        return templates.TemplateResponse(
            request,
            "verify_email.html",
            {"request": request, "email": email, "error": "Account not found.", "message": None, "delivery_mode": None},
            status_code=404,
        )
    if user.email_verified:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"request": request, "error": None, "message": "Email already verified. You can log in now."},
        )
    if not is_otp_valid(user, otp):
        return templates.TemplateResponse(
            request,
            "verify_email.html",
            {
                "request": request,
                "email": email,
                "error": "Invalid or expired OTP. Please try again.",
                "message": None,
                "delivery_mode": None,
            },
            status_code=400,
        )

    clear_email_otp(user)
    db.commit()
    return templates.TemplateResponse(
        request,
        "login.html",
        {"request": request, "error": None, "message": "Email verified successfully. Please log in."},
    )


@router.post("/resend-otp")
async def resend_otp(request: Request, db: Session = Depends(get_db)):
    form = await safe_form_to_dict(request)
    email = (form.get("email") or "").strip().lower()
    user = db.query(StudentRegister).filter(StudentRegister.email == email).first()
    if not user:
        return templates.TemplateResponse(
            request,
            "verify_email.html",
            {"request": request, "email": email, "error": "Account not found.", "message": None, "delivery_mode": None},
            status_code=404,
        )
    delivery_mode = send_verification_otp(user)
    db.commit()
    return templates.TemplateResponse(
        request,
        "verify_email.html",
        {
            "request": request,
            "email": email,
            "error": None,
            "message": "A new OTP has been sent.",
            "delivery_mode": delivery_mode,
        },
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
