from datetime import date
from typing import Optional

from pydantic import BaseModel, EmailStr


class SignupSchema(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    phone: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[date] = None


class LoginSchema(BaseModel):
    email: EmailStr
    password: str


class AIQuerySchema(BaseModel):
    question: str
