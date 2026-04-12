from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


# ── Auth ──────────────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    username: Optional[str] = None        # Phase 3: Beta Electron login identifier
    role: Optional[str] = "ml_engineer"

class UserLogin(BaseModel):
    email: Optional[EmailStr] = None      # Web dashboard login (by email)
    username: Optional[str] = None        # Electron app login (by username)
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int

class UserOut(BaseModel):
    id: int
    email: str
    username: Optional[str]
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


# ── Round Metrics (posted by Team Gamma's gRPC engine) ────────────────────────

class RoundMetricCreate(BaseModel):
    round_number: int
    global_accuracy: float
    num_clients: int = 0

class RoundMetricOut(BaseModel):
    id: int
    job_id: int
    round_number: int
    global_accuracy: float
    num_clients: int
    created_at: datetime

    class Config:
        from_attributes = True
