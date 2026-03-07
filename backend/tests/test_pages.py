"""Tests: pages CRUD and IDOR prevention."""


class TestPagesCRUD:
    def test_create_page(self, client, regular_user, user_headers):
        r = client.post("/api/v1/pages", json={"name": "My Notes"}, headers=user_headers)
        assert r.status_code == 201
        assert r.json()["name"] == "My Notes"

    def test_create_page_name_too_long(self, client, regular_user, user_headers):
        r = client.post("/api/v1/pages", json={"name": "x" * 101}, headers=user_headers)
        assert r.status_code == 422

    def test_list_pages(self, client, regular_user, user_headers, user_page):
        r = client.get("/api/v1/pages", headers=user_headers)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        assert any(p["name"] == "Test Page" for p in data["items"])

    def test_get_page(self, client, regular_user, user_headers, user_page):
        r = client.get(f"/api/v1/pages/{user_page.id}", headers=user_headers)
        assert r.status_code == 200
        assert r.json()["id"] == str(user_page.id)

    def test_update_page(self, client, regular_user, user_headers, user_page):
        r = client.patch(
            f"/api/v1/pages/{user_page.id}",
            json={"name": "Renamed"},
            headers=user_headers,
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Renamed"

    def test_delete_page(self, client, regular_user, user_headers, user_page):
        r = client.delete(f"/api/v1/pages/{user_page.id}", headers=user_headers)
        assert r.status_code == 204
        r2 = client.get(f"/api/v1/pages/{user_page.id}", headers=user_headers)
        assert r2.status_code == 404

    def test_list_only_own_pages(self, client, regular_user, second_user, user_headers, second_user_headers, db):
        from app.models import Page
        other_page = Page(user_id=second_user.id, name="Other's Page")
        db.add(other_page)
        db.commit()
        r = client.get("/api/v1/pages", headers=user_headers)
        names = [p["name"] for p in r.json()["items"]]
        assert "Other's Page" not in names


class TestPagesIDOR:
    def test_cannot_get_other_user_page(self, client, regular_user, second_user, user_headers, db):
        from app.models import Page
        other_page = Page(user_id=second_user.id, name="Private")
        db.add(other_page)
        db.commit()
        r = client.get(f"/api/v1/pages/{other_page.id}", headers=user_headers)
        assert r.status_code == 404

    def test_cannot_update_other_user_page(self, client, second_user, user_headers, db):
        from app.models import Page
        other_page = Page(user_id=second_user.id, name="Private")
        db.add(other_page)
        db.commit()
        r = client.patch(
            f"/api/v1/pages/{other_page.id}",
            json={"name": "Hacked"},
            headers=user_headers,
        )
        assert r.status_code == 404

    def test_cannot_delete_other_user_page(self, client, second_user, user_headers, db):
        from app.models import Page
        other_page = Page(user_id=second_user.id, name="Private")
        db.add(other_page)
        db.commit()
        r = client.delete(f"/api/v1/pages/{other_page.id}", headers=user_headers)
        assert r.status_code == 404
