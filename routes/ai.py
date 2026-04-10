from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models import AIQuery, StudentRegister
from services.dashboard_service import build_student_dashboard_context
from services.ai_service import ask_ai
from utils.form_data import safe_form_to_dict

router = APIRouter(prefix="/ai", tags=["ai"])
templates = Jinja2Templates(directory="templates")


def get_current_user(request: Request, db: Session):
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.query(StudentRegister).filter(StudentRegister.id == user_id).first()


@router.post("/ask")
async def ask_question(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if user.role == "admin":
        return RedirectResponse(url="/admin/dashboard", status_code=303)

    form = await safe_form_to_dict(request)
    question = (form.get("question") or "").strip()
    if not question:
        return RedirectResponse(url="/dashboard", status_code=303)

    response_text = ask_ai(question)

    entry = AIQuery(student_id=user.id, question=question, response=response_text)
    db.add(entry)
    db.commit()
    context = build_student_dashboard_context(
        db,
        user,
        ai_question=question,
        ai_response=response_text,
    )

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "request": request,
            **context,
        },
    )
