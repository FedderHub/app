"""Tests for /auth endpoints, password hashing, and JWT helpers."""
from __future__ import annotations

from datetime import timedelta

import pytest
from jose import jwt

from app.auth import ALGORITHM, create_access_token, hash_password, verify_password
from app.config import SECRET_KEY


class TestRegister:
    def test_register_success(self, client):
        r = client.post(
            "/auth/register",
            json={
                "email": "new@example.com",
                "password": "Password123!",
                "role": "ml_engineer",
            },
        )
        assert r.status_code == 201
        body = r.json()
        assert body["email"] == "new@example.com"
        assert body["role"] == "ml_engineer"
        assert body["status"] == "active"
        assert "id" in body
        assert "password" not in body
        assert "hashed_password" not in body

    def test_register_default_role_is_ml_engineer(self, client):
        r = client.post(
            "/auth/register",
            json={"email": "default@example.com", "password": "Password123!"},
        )
        assert r.status_code == 201
        assert r.json()["role"] == "ml_engineer"

    def test_register_all_valid_roles(self, client):
        for idx, role in enumerate(["platform_admin", "ml_engineer", "client_operator"]):
            r = client.post(
                "/auth/register",
                json={
                    "email": f"role{idx}@example.com",
                    "password": "Password123!",
                    "role": role,
                },
            )
            assert r.status_code == 201, f"role {role} should be accepted"
            assert r.json()["role"] == role

    def test_register_duplicate_email_rejected(self, client):
        payload = {"email": "dup@example.com", "password": "Password123!"}
        r1 = client.post("/auth/register", json=payload)
        assert r1.status_code == 201
        r2 = client.post("/auth/register", json=payload)
        assert r2.status_code == 400
        assert "already registered" in r2.json()["detail"].lower()

    def test_register_invalid_role_rejected(self, client):
        r = client.post(
            "/auth/register",
            json={
                "email": "weird@example.com",
                "password": "Password123!",
                "role": "supreme_overlord",
            },
        )
        assert r.status_code == 400
        assert "invalid role" in r.json()["detail"].lower()

    def test_register_invalid_email_format_rejected(self, client):
        r = client.post(
            "/auth/register",
            json={"email": "not-an-email", "password": "Password123!"},
        )
        assert r.status_code == 422


class TestLogin:
    def test_login_success_returns_jwt(self, client, make_user):
        make_user(email="login@example.com", password="Password123!")
        r = client.post(
            "/auth/login",
            json={"email": "login@example.com", "password": "Password123!"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["token_type"] == "bearer"
        assert body["access_token"]
        assert body["email"] == "login@example.com"
        assert body["role"] == "ml_engineer"
        assert body["status"] == "active"

        decoded = jwt.decode(body["access_token"], SECRET_KEY, algorithms=[ALGORITHM])
        assert decoded["sub"] == str(body["user_id"])
        assert decoded["role"] == "ml_engineer"

    def test_login_wrong_password_unauthorized(self, client, make_user):
        make_user(email="login@example.com", password="Password123!")
        r = client.post(
            "/auth/login",
            json={"email": "login@example.com", "password": "WrongPassword!"},
        )
        assert r.status_code == 401

    def test_login_nonexistent_user_unauthorized(self, client):
        r = client.post(
            "/auth/login",
            json={"email": "ghost@example.com", "password": "anything"},
        )
        assert r.status_code == 401

    def test_login_deactivated_user_forbidden(self, client, make_user):
        make_user(
            email="off@example.com",
            password="Password123!",
            user_status="deactivated",
        )
        r = client.post(
            "/auth/login",
            json={"email": "off@example.com", "password": "Password123!"},
        )
        assert r.status_code == 403


class TestMe:
    def test_me_with_valid_token(self, client, auth_headers):
        headers, user = auth_headers(email="me@example.com")
        r = client.get("/auth/me", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert body["id"] == user.id
        assert body["email"] == "me@example.com"

    def test_me_without_token_unauthorized(self, client):
        r = client.get("/auth/me")
        assert r.status_code == 401

    def test_me_with_garbage_token_unauthorized(self, client):
        r = client.get(
            "/auth/me", headers={"Authorization": "Bearer not.a.real.jwt"}
        )
        assert r.status_code == 401

    def test_me_with_expired_token_unauthorized(self, client, make_user):
        user = make_user(email="exp@example.com")
        token = create_access_token(
            {"sub": str(user.id), "role": user.role},
            expires_delta=timedelta(seconds=-1),
        )
        r = client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 401

    def test_me_with_token_for_deleted_user_unauthorized(self, client, db_session, make_user):
        user = make_user(email="ghost@example.com")
        token = create_access_token({"sub": str(user.id), "role": user.role})
        db_session.delete(user)
        db_session.commit()
        r = client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert r.status_code == 401


class TestAdminUserOps:
    def test_list_users_as_admin(self, client, admin_headers, make_user):
        headers, _ = admin_headers
        make_user(email="other@example.com")
        r = client.get("/auth/users", headers=headers)
        assert r.status_code == 200
        emails = {u["email"] for u in r.json()}
        assert "other@example.com" in emails
        assert "admin@example.com" in emails

    def test_list_users_as_engineer_forbidden(self, client, engineer_headers):
        headers, _ = engineer_headers
        r = client.get("/auth/users", headers=headers)
        assert r.status_code == 403

    def test_list_users_as_client_op_forbidden(self, client, client_op_headers):
        headers, _ = client_op_headers
        r = client.get("/auth/users", headers=headers)
        assert r.status_code == 403

    def test_list_users_unauthenticated(self, client):
        r = client.get("/auth/users")
        assert r.status_code == 401

    @pytest.mark.parametrize("new_status", ["pending", "active", "rejected", "deactivated"])
    def test_update_user_status_accepts_valid_states(
        self, client, admin_headers, make_user, new_status
    ):
        headers, _ = admin_headers
        target = make_user(email=f"target-{new_status}@example.com")
        r = client.patch(
            f"/auth/users/{target.id}/status",
            json={"status": new_status},
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["status"] == new_status

    def test_update_user_status_invalid_value_rejected(
        self, client, admin_headers, make_user
    ):
        headers, _ = admin_headers
        target = make_user(email="target@example.com")
        r = client.patch(
            f"/auth/users/{target.id}/status",
            json={"status": "ascended"},
            headers=headers,
        )
        assert r.status_code == 400

    def test_update_user_status_user_not_found(self, client, admin_headers):
        headers, _ = admin_headers
        r = client.patch(
            "/auth/users/99999/status",
            json={"status": "active"},
            headers=headers,
        )
        assert r.status_code == 404

    def test_update_user_status_as_non_admin_forbidden(
        self, client, engineer_headers, make_user
    ):
        headers, _ = engineer_headers
        target = make_user(email="target@example.com")
        r = client.patch(
            f"/auth/users/{target.id}/status",
            json={"status": "deactivated"},
            headers=headers,
        )
        assert r.status_code == 403


class TestPasswordHelpers:
    def test_hash_password_produces_bcrypt_string(self):
        hashed = hash_password("Password123!")
        assert hashed.startswith("$2")
        assert len(hashed) >= 50

    def test_hash_password_is_non_deterministic(self):
        a = hash_password("same-password")
        b = hash_password("same-password")
        assert a != b
        assert verify_password("same-password", a)
        assert verify_password("same-password", b)

    def test_verify_password_roundtrip(self):
        hashed = hash_password("correct horse battery staple")
        assert verify_password("correct horse battery staple", hashed) is True
        assert verify_password("wrong", hashed) is False


class TestJWTHelpers:
    def test_create_access_token_includes_payload(self):
        token = create_access_token({"sub": "42", "role": "ml_engineer"})
        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert decoded["sub"] == "42"
        assert decoded["role"] == "ml_engineer"
        assert "exp" in decoded

    def test_create_access_token_respects_expires_delta(self):
        token = create_access_token(
            {"sub": "1"}, expires_delta=timedelta(minutes=5)
        )
        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert "exp" in decoded
