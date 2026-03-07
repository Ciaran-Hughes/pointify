"""Tests: login, refresh tokens, password change, lockout, must-change-password."""

from app.auth import hash_password
from app.models import User


class TestLogin:
    def test_login_success(self, client, admin_user):
        r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin123!"})
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_login_wrong_password(self, client, admin_user):
        r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"})
        assert r.status_code == 401
        assert r.json()["detail"]["error_code"] == "INVALID_CREDENTIALS"

    def test_login_unknown_user(self, client):
        r = client.post("/api/v1/auth/login", json={"username": "ghost", "password": "pass"})
        assert r.status_code == 401

    def test_login_disabled_user(self, client, regular_user, db):
        regular_user.is_active = False
        db.commit()
        r = client.post("/api/v1/auth/login", json={"username": "testuser", "password": "User123!"})
        assert r.status_code == 401
        assert r.json()["detail"]["error_code"] == "ACCOUNT_DISABLED"

    def test_login_returns_must_change_flag(self, client, db):
        user = User(
            username="newuser",
            password_hash=hash_password("Pass123!"),
            role="user",
            must_change_password=True,
            is_active=True,
        )
        db.add(user)
        db.commit()
        r = client.post("/api/v1/auth/login", json={"username": "newuser", "password": "Pass123!"})
        assert r.status_code == 200
        assert r.json()["must_change_password"] is True


class TestRefreshToken:
    def test_refresh_success(self, client, admin_user):
        login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin123!"})
        refresh_token = login.json()["refresh_token"]
        r = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_refresh_returns_new_refresh_token(self, client, admin_user):
        """Response must include refresh_token so clients can perform chained rotation."""
        login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin123!"})
        refresh_token = login.json()["refresh_token"]
        r = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert r.status_code == 200
        data = r.json()
        assert "refresh_token" in data
        assert data["refresh_token"] != refresh_token  # rotated to a new value

    def test_chained_rotation_succeeds(self, client, admin_user):
        """A second silent-refresh using the token returned by the first must succeed."""
        login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin123!"})
        first_refresh = login.json()["refresh_token"]

        r1 = client.post("/api/v1/auth/refresh", json={"refresh_token": first_refresh})
        assert r1.status_code == 200
        second_refresh = r1.json()["refresh_token"]

        r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": second_refresh})
        assert r2.status_code == 200
        assert "access_token" in r2.json()

    def test_old_refresh_token_rejected_after_rotation(self, client, admin_user):
        """The consumed token must not be reusable after rotation."""
        login = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin123!"})
        first_refresh = login.json()["refresh_token"]

        r1 = client.post("/api/v1/auth/refresh", json={"refresh_token": first_refresh})
        assert r1.status_code == 200

        # Replay the already-consumed token — must be rejected
        r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": first_refresh})
        assert r2.status_code == 401

    def test_refresh_invalid_token(self, client):
        r = client.post("/api/v1/auth/refresh", json={"refresh_token": "notvalid"})
        assert r.status_code == 401

    def test_refresh_revoked_after_disable(self, client, regular_user, admin_user, db, admin_headers):
        login = client.post("/api/v1/auth/login", json={"username": "testuser", "password": "User123!"})
        refresh_token = login.json()["refresh_token"]
        client.post(f"/api/v1/admin/users/{regular_user.id}/disable", headers=admin_headers)
        r = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert r.status_code == 401


class TestPasswordChange:
    def test_change_success(self, client, admin_user, admin_headers):
        r = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "Admin123!", "new_password": "NewPass456!"},
            headers=admin_headers,
        )
        assert r.status_code == 200

    def test_change_wrong_current(self, client, admin_user, admin_headers):
        r = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "wrong", "new_password": "NewPass456!"},
            headers=admin_headers,
        )
        assert r.status_code == 400

    def test_change_too_short(self, client, admin_user, admin_headers):
        r = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "Admin123!", "new_password": "sh0Rt"},
            headers=admin_headers,
        )
        assert r.status_code == 422

    def test_change_no_uppercase(self, client, admin_user, admin_headers):
        r = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "Admin123!", "new_password": "alllower1!"},
            headers=admin_headers,
        )
        assert r.status_code == 422

    def test_change_no_digit(self, client, admin_user, admin_headers):
        r = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "Admin123!", "new_password": "NoDigitsHere!"},
            headers=admin_headers,
        )
        assert r.status_code == 422


class TestMustChangePassword:
    def test_blocked_on_protected_routes(self, client, db):
        user = User(
            username="mustchange",
            password_hash=hash_password("Pass123!"),
            role="user",
            must_change_password=True,
            is_active=True,
        )
        db.add(user)
        db.commit()
        login = client.post("/api/v1/auth/login", json={"username": "mustchange", "password": "Pass123!"})
        token = login.json()["access_token"]
        r = client.get("/api/v1/pages", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 403
        assert r.json()["detail"]["error_code"] == "PASSWORD_CHANGE_REQUIRED"

    def test_change_password_allowed_during_must_change(self, client, db):
        user = User(
            username="mustchange2",
            password_hash=hash_password("Pass123!"),
            role="user",
            must_change_password=True,
            is_active=True,
        )
        db.add(user)
        db.commit()
        login = client.post("/api/v1/auth/login", json={"username": "mustchange2", "password": "Pass123!"})
        token = login.json()["access_token"]
        r = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "Pass123!", "new_password": "NewPass789!"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200


class TestNoAuth:
    def test_no_token_returns_401(self, client):
        assert client.get("/api/v1/pages").status_code == 401

    def test_invalid_token_returns_401(self, client):
        r = client.get("/api/v1/pages", headers={"Authorization": "Bearer bad"})
        assert r.status_code == 401


class TestUserPreferences:
    def test_update_language_success(self, client, regular_user, user_headers):
        r = client.patch(
            "/api/v1/auth/me/preferences",
            json={"whisper_language": "fi"},
            headers=user_headers,
        )
        assert r.status_code == 200
        assert r.json()["whisper_language"] == "fi"

    def test_update_language_auto(self, client, regular_user, user_headers):
        r = client.patch(
            "/api/v1/auth/me/preferences",
            json={"whisper_language": "auto"},
            headers=user_headers,
        )
        assert r.status_code == 200
        assert r.json()["whisper_language"] == "auto"

    def test_update_invalid_language_returns_422(self, client, regular_user, user_headers):
        r = client.patch(
            "/api/v1/auth/me/preferences",
            json={"whisper_language": "xx"},
            headers=user_headers,
        )
        assert r.status_code == 422

    def test_update_preferences_unauthenticated(self, client):
        r = client.patch(
            "/api/v1/auth/me/preferences",
            json={"whisper_language": "en"},
        )
        assert r.status_code == 401

    def test_me_includes_whisper_language(self, client, regular_user, user_headers):
        r = client.get("/api/v1/auth/me", headers=user_headers)
        assert r.status_code == 200
        assert "whisper_language" in r.json()
        assert r.json()["whisper_language"] == "en"
