from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


# ── Auth ──────────────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    role: Optional[str] = "ml_engineer"

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int

class UserOut(BaseModel):
    id: int
    email: str
    role: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


# ── Jobs ──────────────────────────────────────────────────────────────────────

class JobCreate(BaseModel):
    job_name: str
    round_count: int = 5
    local_epochs: int = 3

class JobOut(BaseModel):
    id: int
    job_name: str
    round_count: int
    local_epochs: int
    status: str
    created_by: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True
