"""Shared pytest fixtures."""

import tempfile
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.auth import create_access_token, hash_password
from app.database import Base, get_db
from app.limiter import limiter
from app.main import app
from app.models import AppSettings, Page, User

# Use a temp file so tests are fully isolated from the production DB at data/pointify.db.
# A new file is created per pytest session and deleted on exit.
_tmp_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False, prefix="test_pointify_")
_tmp_db_file.close()
TEST_DB_URL = f"sqlite:///{_tmp_db_file.name}"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def pytest_sessionfinish(session, exitstatus):  # noqa: ARG001
    """Remove the temp test DB after the full pytest session."""
    try:
        os.unlink(_tmp_db_file.name)
    except OSError:
        pass


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    if not db.query(AppSettings).first():
        db.add(AppSettings(default_whisper_model="base", ollama_model="gpt-oss:20b"))
        db.commit()
    # Disable rate limiting so tests don't hit 429
    original_enabled = limiter.enabled
    limiter.enabled = False
    with TestClient(app) as c:
        yield c
    limiter.enabled = original_enabled
    app.dependency_overrides.clear()


@pytest.fixture
def admin_user(db):
    user = User(
        username="admin",
        password_hash=hash_password("Admin123!"),
        role="admin",
        must_change_password=False,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def regular_user(db):
    user = User(
        username="testuser",
        password_hash=hash_password("User123!"),
        role="user",
        must_change_password=False,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def second_user(db):
    user = User(
        username="otheruser",
        password_hash=hash_password("Other123!"),
        role="user",
        must_change_password=False,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def admin_token(admin_user):
    return create_access_token(admin_user.id, admin_user.role)


@pytest.fixture
def user_token(regular_user):
    return create_access_token(regular_user.id, regular_user.role)


@pytest.fixture
def second_user_token(second_user):
    return create_access_token(second_user.id, second_user.role)


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def user_headers(user_token):
    return {"Authorization": f"Bearer {user_token}"}


@pytest.fixture
def second_user_headers(second_user_token):
    return {"Authorization": f"Bearer {second_user_token}"}


@pytest.fixture
def user_page(regular_user, db):
    page = Page(user_id=regular_user.id, name="Test Page")
    db.add(page)
    db.commit()
    db.refresh(page)
    return page
