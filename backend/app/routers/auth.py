from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models
from app.schemas import UserRegister, UserLogin, TokenResponse, UserOut
from app.auth import (
    get_db,
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    lookup_user,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    """Register a new user. Roles: platform_admin | ml_engineer | client_operator."""
    existing = db.query(models.User).filter(models.User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    if payload.username:
        existing_username = db.query(models.User).filter(
            models.User.username == payload.username
        ).first()
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken",
            )

    allowed_roles = {"platform_admin", "ml_engineer", "client_operator"}
    if payload.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Choose from: {allowed_roles}",
        )

    user = models.User(
        email=payload.email,
        username=payload.username,
        hashed_password=hash_password(payload.password),
        role=payload.role,
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticate and receive a JWT access token.
    Phase 3: accepts email (web dashboard) OR username (Beta Electron app).
    """
    identifier = payload.email or payload.username
    if not identifier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either email or username to log in.",
        )

    user = lookup_user(str(identifier), db)
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(data={"sub": str(user.id), "role": user.role})
    return TokenResponse(access_token=token, role=user.role, user_id=user.id)


@router.get("/me", response_model=UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    """Return the currently authenticated user's profile."""
    return current_user
