from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime

from database import get_db
from models import (
    Attendance,
    Student,
    StudentRegister,
)
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
    return templates.TemplateResponse(request, "signup.html", {"request": request, "error": None})


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
    )
    db.add(user)
    db.flush()

    # Keep legacy students table synced for compatibility with existing modules.
    db.add(Student(name=full_name, email=email, password=hashed_password, role="student"))
    db.commit()

    request.session["user_id"] = user.id
    request.session["user_name"] = user.full_name
    request.session["role"] = "student"
    return RedirectResponse(url="/dashboard", status_code=303)


@router.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"request": request, "error": None})


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
            {"request": request, "error": "Invalid email or password."},
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
