"""Tests: admin user CRUD, soft-delete, re-enable, audit, settings."""

from app.models import User


class TestAdminUserCRUD:
    def test_list_users(self, client, admin_user, admin_headers):
        r = client.get("/api/v1/admin/users", headers=admin_headers)
        assert r.status_code == 200
        assert len(r.json()) >= 1

    def test_list_users_requires_admin(self, client, regular_user, user_headers):
        r = client.get("/api/v1/admin/users", headers=user_headers)
        assert r.status_code == 403

    def test_create_user(self, client, admin_user, admin_headers):
        r = client.post(
            "/api/v1/admin/users",
            json={"username": "newbie", "password": "Secure123!", "role": "user"},
            headers=admin_headers,
        )
        assert r.status_code == 201
        data = r.json()
        assert data["username"] == "newbie"
        assert data["must_change_password"] is True

    def test_create_user_duplicate_username(self, client, admin_user, regular_user, admin_headers):
        r = client.post(
            "/api/v1/admin/users",
            json={"username": "testuser", "password": "Secure123!", "role": "user"},
            headers=admin_headers,
        )
        assert r.status_code == 409
        assert r.json()["detail"]["error_code"] == "USERNAME_TAKEN"

    def test_create_user_weak_password(self, client, admin_user, admin_headers):
        r = client.post(
            "/api/v1/admin/users",
            json={"username": "newbie2", "password": "weak", "role": "user"},
            headers=admin_headers,
        )
        assert r.status_code == 422

    def test_reset_password(self, client, admin_user, regular_user, admin_headers):
        r = client.post(
            f"/api/v1/admin/users/{regular_user.id}/reset-password",
            json={"new_password": "Reset123!"},
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["must_change_password"] is True


class TestSoftDelete:
    def test_disable_user(self, client, admin_user, regular_user, admin_headers, db):
        r = client.post(f"/api/v1/admin/users/{regular_user.id}/disable", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["is_active"] is False
        db.refresh(regular_user)
        assert not regular_user.is_active
        assert regular_user.disabled_at is not None

    def test_disabled_user_cannot_login(self, client, admin_user, regular_user, admin_headers):
        client.post(f"/api/v1/admin/users/{regular_user.id}/disable", headers=admin_headers)
        r = client.post("/api/v1/auth/login", json={"username": "testuser", "password": "User123!"})
        assert r.status_code == 401

    def test_data_preserved_after_disable(self, client, admin_user, regular_user, admin_headers, user_page, db):
        client.post(f"/api/v1/admin/users/{regular_user.id}/disable", headers=admin_headers)
        from app.models import Page
        pages = db.query(Page).filter(Page.user_id == regular_user.id).all()
        assert len(pages) > 0

    def test_enable_user(self, client, admin_user, regular_user, admin_headers, db):
        client.post(f"/api/v1/admin/users/{regular_user.id}/disable", headers=admin_headers)
        r = client.post(f"/api/v1/admin/users/{regular_user.id}/enable", headers=admin_headers)
        assert r.status_code == 200
        assert r.json()["is_active"] is True
        db.refresh(regular_user)
        assert regular_user.is_active
        assert regular_user.disabled_at is None

    def test_cannot_disable_self(self, client, admin_user, admin_headers):
        r = client.post(f"/api/v1/admin/users/{admin_user.id}/disable", headers=admin_headers)
        assert r.status_code == 400
        assert r.json()["detail"]["error_code"] == "SELF_DISABLE"


class TestAdminSettings:
    def test_get_settings(self, client, admin_user, admin_headers):
        r = client.get("/api/v1/admin/settings", headers=admin_headers)
        assert r.status_code == 200
        assert "default_whisper_model" in r.json()

    def test_update_settings(self, client, admin_user, admin_headers):
        r = client.patch(
            "/api/v1/admin/settings",
            json={"default_whisper_model": "small"},
            headers=admin_headers,
        )
        assert r.status_code == 200
        assert r.json()["default_whisper_model"] == "small"

    def test_update_invalid_whisper_model(self, client, admin_user, admin_headers):
        r = client.patch(
            "/api/v1/admin/settings",
            json={"default_whisper_model": "gigantic"},
            headers=admin_headers,
        )
        assert r.status_code == 422
