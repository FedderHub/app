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
    email: str
    status: str

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
    creator_email: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class JobStartResponse(BaseModel):
    job_id: int
    status: str
    task_id: Optional[str] = None
    message: str

class RoundMetricOut(BaseModel):
    id: int
    job_id: int
    round_number: int
    accuracy: Optional[float] = None
    loss: Optional[float] = None
    num_clients: Optional[int] = None
    total_samples: Optional[int] = None
    global_weights_snapshot: Optional[str] = None
    completed_at: datetime

    class Config:
        from_attributes = True


class UserStatusUpdate(BaseModel):
    status: str
