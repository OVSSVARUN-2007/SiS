import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request
from starlette.middleware.sessions import SessionMiddleware

from config import get_settings
from database import Base, engine, ensure_schema_upgrade
from routes.admin import router as admin_router
from routes.ai import router as ai_router
from routes.student import router as student_router

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.enable_startup_schema_sync:
        Base.metadata.create_all(bind=engine)
        ensure_schema_upgrade()
    yield

app = FastAPI(title="SiS - Student Information System", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key)
templates = Jinja2Templates(directory="templates")

app.include_router(student_router)
app.include_router(admin_router)
app.include_router(ai_router)

if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def root(request: Request):
    return templates.TemplateResponse(request, "home.html", {"request": request})
