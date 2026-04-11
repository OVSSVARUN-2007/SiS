import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
from starlette.middleware.sessions import SessionMiddleware

from config import get_settings
from database import ensure_database_ready
from routes.admin import router as admin_router
from routes.ai import router as ai_router
from routes.api_v2 import router as api_v2_router
from routes.student import router as student_router

settings = get_settings()
ensure_database_ready()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_database_ready()
    yield

app = FastAPI(title="SiS - Student Information System", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)
templates = Jinja2Templates(directory="templates")

app.include_router(student_router)
app.include_router(admin_router)
app.include_router(ai_router)
app.include_router(api_v2_router)

if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def root(request: Request):
    return templates.TemplateResponse(request, "home.html", {"request": request})
