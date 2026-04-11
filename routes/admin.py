from datetime import datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from config import get_settings
from models import Assignment, Attendance, Course, Document, Notice, StudentRegister
from services.verification_service import send_verification_otp
from utils.form_data import safe_form_to_dict
from utils.security import hash_password, verify_password

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="templates")
ADMIN_SETUP_KEY = get_settings().admin_setup_key


def parse_int(value: str | None) -> int | None:
    if value and value.strip().isdigit():
        return int(value.strip())
    return None


def parse_date(value: str | None):
    if not value or not value.strip():
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None


def get_admin_user(request: Request, db: Session):
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    user = db.query(StudentRegister).filter(StudentRegister.id == user_id).first()
    if not user or user.role != "admin":
        return None
    return user


def has_any_admin(db: Session) -> bool:
    return db.query(StudentRegister).filter(StudentRegister.role == "admin").first() is not None


def render_admin_dashboard(request: Request, db: Session, admin_user, error: str | None = None):
    filters = {
        "department": (request.query_params.get("department") or "").strip(),
        "academic_year": (request.query_params.get("academic_year") or "").strip(),
        "section": (request.query_params.get("section") or "").strip(),
    }

    students_query = db.query(StudentRegister).filter(StudentRegister.role == "student")
    if filters["department"]:
        students_query = students_query.filter(StudentRegister.department == filters["department"])
    if filters["academic_year"].isdigit():
        students_query = students_query.filter(StudentRegister.academic_year == int(filters["academic_year"]))
    if filters["section"]:
        students_query = students_query.filter(StudentRegister.section == filters["section"])

    students = students_query.order_by(StudentRegister.full_name.asc()).all()
    courses = db.query(Course).order_by(Course.title.asc()).all()
    assignments = db.query(Assignment).order_by(Assignment.id.desc()).limit(20).all()
    attendance_rows = db.query(Attendance).order_by(Attendance.id.desc()).limit(20).all()
    notices = db.query(Notice).order_by(Notice.id.desc()).limit(20).all()
    documents = db.query(Document).order_by(Document.id.desc()).limit(20).all()

    return templates.TemplateResponse(
        request,
        "admin_dashboard.html",
        {
            "request": request,
            "admin_user": admin_user,
            "students": students,
            "courses": courses,
            "assignments": assignments,
            "attendance_rows": attendance_rows,
            "notices": notices,
            "documents": documents,
            "filters": filters,
            "error": error,
        },
    )


@router.get("/signup")
def admin_signup_page(request: Request, db: Session = Depends(get_db)):
    require_key = has_any_admin(db)
    if require_key and not ADMIN_SETUP_KEY:
        return RedirectResponse(url="/admin/login", status_code=303)
    return templates.TemplateResponse(
        request,
        "admin_signup.html",
        {"request": request, "error": None, "message": None, "require_setup_key": require_key},
    )


@router.post("/signup")
async def admin_signup(request: Request, db: Session = Depends(get_db)):
    form = await safe_form_to_dict(request)
    full_name = (form.get("full_name") or "").strip()
    email = (form.get("email") or "").strip().lower()
    password = form.get("password") or ""
    setup_key = (form.get("setup_key") or "").strip()
    require_key = has_any_admin(db)

    if require_key and not ADMIN_SETUP_KEY:
        return RedirectResponse(url="/admin/login", status_code=303)

    if require_key and setup_key != ADMIN_SETUP_KEY:
        return templates.TemplateResponse(
            request,
            "admin_signup.html",
            {"request": request, "error": "Invalid admin setup key.", "message": None, "require_setup_key": True},
            status_code=403,
        )

    if not full_name or not email or not password:
        return templates.TemplateResponse(
            request,
            "admin_signup.html",
            {"request": request, "error": "Name, email and password are required.", "message": None, "require_setup_key": require_key},
            status_code=400,
        )

    existing = db.query(StudentRegister).filter(StudentRegister.email == email).first()
    if existing:
        return templates.TemplateResponse(
            request,
            "admin_signup.html",
            {"request": request, "error": "Email already exists.", "message": None, "require_setup_key": require_key},
            status_code=400,
        )

    admin_user = StudentRegister(
        full_name=full_name,
        email=email,
        password=hash_password(password),
        role="admin",
        is_active=1,
        email_verified=0,
    )
    db.add(admin_user)
    delivery_mode = send_verification_otp(admin_user)
    db.commit()

    return templates.TemplateResponse(
        request,
        "verify_email.html",
        {
            "request": request,
            "email": email,
            "error": None,
            "message": "Admin account created. Please verify your email to continue.",
            "delivery_mode": delivery_mode,
        },
        status_code=201,
    )


@router.get("/login")
def admin_login_page(request: Request):
    return templates.TemplateResponse(request, "admin_login.html", {"request": request, "error": None, "message": None})


@router.post("/login")
async def admin_login(request: Request, db: Session = Depends(get_db)):
    form = await safe_form_to_dict(request)
    email = (form.get("email") or "").strip().lower()
    password = form.get("password") or ""

    user = db.query(StudentRegister).filter(StudentRegister.email == email).first()
    if not user or user.role != "admin" or not verify_password(password, user.password):
        return templates.TemplateResponse(
            request,
            "admin_login.html",
            {"request": request, "error": "Invalid admin credentials.", "message": None},
            status_code=401,
        )
    if not user.email_verified:
        return templates.TemplateResponse(
            request,
            "admin_login.html",
            {
                "request": request,
                "error": "Please verify your email before logging in.",
                "message": f"Use the OTP sent to {user.email} or request a new one.",
            },
            status_code=403,
        )

    request.session["user_id"] = user.id
    request.session["user_name"] = user.full_name
    request.session["role"] = "admin"
    return RedirectResponse(url="/admin/dashboard", status_code=303)


@router.get("/dashboard")
def admin_dashboard(request: Request, db: Session = Depends(get_db)):
    admin_user = get_admin_user(request, db)
    if not admin_user:
        return RedirectResponse(url="/admin/login", status_code=303)
    return render_admin_dashboard(request, db, admin_user)


@router.post("/courses")
async def create_course(request: Request, db: Session = Depends(get_db)):
    admin_user = get_admin_user(request, db)
    if not admin_user:
        return RedirectResponse(url="/admin/login", status_code=303)

    form = await safe_form_to_dict(request)
    title = (form.get("title") or "").strip()
    description = (form.get("description") or "").strip() or None
    instructor = (form.get("instructor") or "").strip() or None

    if not title:
        return render_admin_dashboard(request, db, admin_user, "Course title is required.")

    db.add(Course(title=title, description=description, instructor=instructor))
    db.commit()
    return RedirectResponse(url="/admin/dashboard", status_code=303)


@router.post("/assignments")
async def create_assignment(request: Request, db: Session = Depends(get_db)):
    admin_user = get_admin_user(request, db)
    if not admin_user:
        return RedirectResponse(url="/admin/login", status_code=303)

    form = await safe_form_to_dict(request)
    title = (form.get("title") or "").strip()
    due_date = parse_date(form.get("due_date"))
    course_id = parse_int(form.get("course_id"))
    department = (form.get("department") or "").strip() or None
    section = (form.get("section") or "").strip() or None
    academic_year = parse_int(form.get("academic_year"))
    description = (form.get("description") or "").strip() or None

    if not title:
        return render_admin_dashboard(request, db, admin_user, "Assignment title is required.")

    db.add(
        Assignment(
            course_id=course_id,
            title=title,
            description=description,
            due_date=due_date,
            department=department,
            academic_year=academic_year,
            section=section,
        )
    )
    db.commit()
    return RedirectResponse(url="/admin/dashboard", status_code=303)


@router.post("/attendance")
async def mark_attendance(request: Request, db: Session = Depends(get_db)):
    admin_user = get_admin_user(request, db)
    if not admin_user:
        return RedirectResponse(url="/admin/login", status_code=303)

    form = await safe_form_to_dict(request)
    student_id = parse_int(form.get("student_id"))
    course_id = parse_int(form.get("course_id"))
    status = (form.get("status") or "").strip().lower()
    date_value = parse_date(form.get("date"))

    student = (
        db.query(StudentRegister)
        .filter(StudentRegister.id == student_id, StudentRegister.role == "student")
        .first()
    )
    if not student:
        return render_admin_dashboard(request, db, admin_user, "Invalid student selected.")
    if status not in {"present", "absent"}:
        return render_admin_dashboard(request, db, admin_user, "Attendance status must be present/absent.")
    if not date_value:
        return render_admin_dashboard(request, db, admin_user, "A valid attendance date is required.")

    db.add(
        Attendance(
            student_id=student.id,
            course_id=course_id,
            date=date_value,
            status=status,
            department=student.department,
            academic_year=student.academic_year,
            section=student.section,
            marked_by=admin_user.id,
        )
    )
    db.commit()
    return RedirectResponse(url="/admin/dashboard", status_code=303)


@router.post("/notices")
async def create_notice(request: Request, db: Session = Depends(get_db)):
    admin_user = get_admin_user(request, db)
    if not admin_user:
        return RedirectResponse(url="/admin/login", status_code=303)

    form = await safe_form_to_dict(request)
    title = (form.get("title") or "").strip()
    message = (form.get("message") or "").strip()
    category = (form.get("category") or "notice").strip().lower()
    department = (form.get("department") or "").strip() or None
    section = (form.get("section") or "").strip() or None
    academic_year = parse_int(form.get("academic_year"))

    if not title or not message:
        return render_admin_dashboard(request, db, admin_user, "Notice title and message are required.")
    if category not in {"notice", "internship", "job"}:
        category = "notice"

    db.add(
        Notice(
            title=title,
            message=message,
            category=category,
            department=department,
            academic_year=academic_year,
            section=section,
            created_by=admin_user.id,
        )
    )
    db.commit()
    return RedirectResponse(url="/admin/dashboard", status_code=303)


@router.post("/documents")
async def create_document(request: Request, db: Session = Depends(get_db)):
    admin_user = get_admin_user(request, db)
    if not admin_user:
        return RedirectResponse(url="/admin/login", status_code=303)

    form = await safe_form_to_dict(request)
    title = (form.get("title") or "").strip()
    file_url = (form.get("file_url") or "").strip()
    description = (form.get("description") or "").strip() or None
    category = (form.get("category") or "document").strip().lower()
    department = (form.get("department") or "").strip() or None
    section = (form.get("section") or "").strip() or None
    academic_year = parse_int(form.get("academic_year"))

    if not title or not file_url:
        return render_admin_dashboard(request, db, admin_user, "Document title and URL are required.")
    if category not in {"document", "internship", "job"}:
        category = "document"

    db.add(
        Document(
            title=title,
            description=description,
            file_url=file_url,
            category=category,
            department=department,
            academic_year=academic_year,
            section=section,
            created_by=admin_user.id,
        )
    )
    db.commit()
    return RedirectResponse(url="/admin/dashboard", status_code=303)
