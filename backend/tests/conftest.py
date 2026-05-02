"""Shared pytest fixtures for FederHub backend tests.

Strategy
--------
* Use an in-memory SQLite engine with ``StaticPool`` so every test session
  shares the same connection / schema.
* Override the ``get_db`` FastAPI dependency to point at the test session,
  so production AWS RDS is never touched during testing.
* Each test function gets a freshly created schema (``create_all``) and a
  full teardown (``drop_all``) for full isolation.

Run from the ``backend/`` directory:

    pytest tests/ -v --cov=app --cov-report=term-missing
"""
from __future__ import annotations

import os
import warnings

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret-do-not-use-in-prod")

warnings.filterwarnings(
    "ignore",
    message=".*error reading bcrypt version.*",
)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: E402
from app.auth import create_access_token, get_db, hash_password  # noqa: E402
from app.db import Base  # noqa: E402
from app.main import app  # noqa: E402


_TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_TestSession = sessionmaker(autocommit=False, autoflush=False, bind=_TEST_ENGINE)


@pytest.fixture(scope="function")
def db_session():
    """Provide a fresh DB schema per test; tear it down afterwards."""
    Base.metadata.create_all(bind=_TEST_ENGINE)
    session = _TestSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=_TEST_ENGINE)


@pytest.fixture(scope="function")
def client(db_session):
    """TestClient with ``get_db`` overridden to use the in-memory test session."""

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _make_user(
    db,
    *,
    email: str,
    password: str = "Password123!",
    role: str = "ml_engineer",
    user_status: str = "active",
) -> models.User:
    user = models.User(
        email=email,
        hashed_password=hash_password(password),
        role=role,
        status=user_status,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _token_for(user: models.User) -> str:
    return create_access_token(data={"sub": str(user.id), "role": user.role})


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def make_user(db_session):
    """Factory for creating users with arbitrary roles / statuses."""

    def _factory(**kwargs):
        return _make_user(db_session, **kwargs)

    return _factory


@pytest.fixture
def auth_headers(make_user):
    """Factory: create a user and return ``(headers, user)``."""

    def _factory(**kwargs):
        user = make_user(**kwargs)
        token = _token_for(user)
        return _auth_header(token), user

    return _factory


@pytest.fixture
def admin_headers(auth_headers):
    headers, user = auth_headers(email="admin@example.com", role="platform_admin")
    return headers, user


@pytest.fixture
def engineer_headers(auth_headers):
    headers, user = auth_headers(email="engineer@example.com", role="ml_engineer")
    return headers, user


@pytest.fixture
def client_op_headers(auth_headers):
    headers, user = auth_headers(email="client@example.com", role="client_operator")
    return headers, user
