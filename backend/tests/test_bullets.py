"""Tests: bullet points CRUD, reorder, IDOR, day deletion."""

import time
from datetime import date

from app.models import BulletPoint, Page, Recording


def _make_recording(db, page_id, day=None):
    import uuid
    rec = Recording(
        page_id=page_id,
        recorded_date=day or date.today(),
        audio_path=f"data/audio/{uuid.uuid4()}.audio",
        transcript="Test transcript.",
        whisper_model="base",
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def _make_bullet(db, page_id, recording_id=None, text="Test bullet", sort_order=0, day=None):
    bp = BulletPoint(
        page_id=page_id,
        recording_id=recording_id,
        day=day or date.today(),
        text=text,
        sort_order=sort_order,
    )
    db.add(bp)
    db.commit()
    db.refresh(bp)
    return bp


class TestBulletCRUD:
    def test_add_bullet_manually(self, client, regular_user, user_headers, user_page):
        r = client.post(
            f"/api/v1/pages/{user_page.id}/bullets",
            json={"text": "My idea", "day": str(date.today())},
            headers=user_headers,
        )
        assert r.status_code == 201
        assert r.json()["text"] == "My idea"

    def test_add_bullet_text_too_long(self, client, regular_user, user_headers, user_page):
        r = client.post(
            f"/api/v1/pages/{user_page.id}/bullets",
            json={"text": "x" * 2001, "day": str(date.today())},
            headers=user_headers,
        )
        assert r.status_code == 422

    def test_edit_bullet(self, client, regular_user, user_headers, user_page, db):
        bp = _make_bullet(db, user_page.id)
        r = client.patch(f"/api/v1/bullets/{bp.id}", json={"text": "Edited"}, headers=user_headers)
        assert r.status_code == 200
        assert r.json()["text"] == "Edited"

    def test_delete_bullet(self, client, regular_user, user_headers, user_page, db):
        bp = _make_bullet(db, user_page.id)
        r = client.delete(f"/api/v1/bullets/{bp.id}", headers=user_headers)
        assert r.status_code == 204

    def test_reorder_bullets(self, client, regular_user, user_headers, user_page, db):
        b1 = _make_bullet(db, user_page.id, text="First", sort_order=0)
        b2 = _make_bullet(db, user_page.id, text="Second", sort_order=1)
        r = client.patch(
            f"/api/v1/pages/{user_page.id}/bullets/reorder",
            json={"ordered_ids": [str(b2.id), str(b1.id)]},
            headers=user_headers,
        )
        assert r.status_code == 200
        result = {b["id"]: b["sort_order"] for b in r.json()}
        assert result[str(b2.id)] == 0
        assert result[str(b1.id)] == 1

    def test_get_page_by_days(self, client, regular_user, user_headers, user_page, db):
        rec = _make_recording(db, user_page.id)
        _make_bullet(db, user_page.id, recording_id=rec.id, text="Day bullet")
        r = client.get(f"/api/v1/pages/{user_page.id}/days", headers=user_headers)
        assert r.status_code == 200
        days = r.json()
        assert len(days) >= 1
        # bullets now live inside groups[].bullets, not at the top level
        all_bullets = [b for d in days for g in d["groups"] for b in g["bullets"]]
        assert any(b["text"] == "Day bullet" for b in all_bullets)

    def test_recordings_within_day_ordered_latest_first(self, client, regular_user, user_headers, user_page, db):
        today = str(date.today())
        rec1 = _make_recording(db, user_page.id, day=date.today())
        _make_bullet(db, user_page.id, recording_id=rec1.id, text="First recording", day=date.today())
        time.sleep(1.1)  # ensure rec2 has strictly later created_at (DB often second precision)
        rec2 = _make_recording(db, user_page.id, day=date.today())
        _make_bullet(db, user_page.id, recording_id=rec2.id, text="Second recording", day=date.today())
        r = client.get(f"/api/v1/pages/{user_page.id}/days", headers=user_headers)
        assert r.status_code == 200
        days = r.json()
        day_group = next((d for d in days if d["day"] == today), None)
        assert day_group is not None
        groups = day_group["groups"]
        assert len(groups) == 2
        assert groups[0]["recording"]["id"] == str(rec2.id)
        assert groups[1]["recording"]["id"] == str(rec1.id)


class TestBulletIDOR:
    def test_cannot_edit_other_users_bullet(self, client, second_user, user_headers, db):
        other_page = Page(user_id=second_user.id, name="Other")
        db.add(other_page)
        db.commit()
        bp = _make_bullet(db, other_page.id)
        r = client.patch(f"/api/v1/bullets/{bp.id}", json={"text": "Hacked"}, headers=user_headers)
        assert r.status_code == 404

    def test_cannot_delete_other_users_bullet(self, client, second_user, user_headers, db):
        other_page = Page(user_id=second_user.id, name="Other")
        db.add(other_page)
        db.commit()
        bp = _make_bullet(db, other_page.id)
        r = client.delete(f"/api/v1/bullets/{bp.id}", headers=user_headers)
        assert r.status_code == 404

    def test_cannot_add_bullet_to_other_users_page(self, client, second_user, user_headers, db):
        other_page = Page(user_id=second_user.id, name="Other")
        db.add(other_page)
        db.commit()
        r = client.post(
            f"/api/v1/pages/{other_page.id}/bullets",
            json={"text": "Hacked", "day": str(date.today())},
            headers=user_headers,
        )
        assert r.status_code == 404


class TestDayDeletion:
    def test_delete_day_archives_recording_keeps_bullets(self, client, regular_user, user_headers, user_page, db):
        rec = _make_recording(db, user_page.id)
        _make_bullet(db, user_page.id, recording_id=rec.id)
        _make_bullet(db, user_page.id, recording_id=rec.id)
        r = client.delete(f"/api/v1/recordings/{rec.id}/day", headers=user_headers)
        assert r.status_code == 204
        db.refresh(rec)
        assert rec.archived_at is not None
        # bullets are preserved (soft-delete keeps data)
        remaining = db.query(BulletPoint).filter(BulletPoint.recording_id == rec.id).all()
        assert len(remaining) == 2
