import os

os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import User, UserRole
from app.security import hash_passcode


engine = create_engine(
    os.environ["DATABASE_URL"],
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def _override_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def _seed_user():
    db = TestingSessionLocal()
    db.query(User).delete()
    user = User(
        user_id="testuser",
        passcode_hash=hash_passcode("pass1234"),
        display_name="テスト太郎",
        role=UserRole.USER,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.close()


def test_login_success_redirect_dashboard():
    app.dependency_overrides[get_db] = _override_db
    _seed_user()

    client = TestClient(app)
    response = client.post(
        "/login",
        data={"user_id": "testuser", "passcode": "pass1234"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"


def test_login_failure_redirect_login():
    app.dependency_overrides[get_db] = _override_db
    client = TestClient(app)
    response = client.post(
        "/login",
        data={"user_id": "wrong", "passcode": "wrong"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_protected_redirects_to_login():
    client = TestClient(app)
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_logout_clears_session():
    app.dependency_overrides[get_db] = _override_db
    _seed_user()

    client = TestClient(app)
    client.post("/login", data={"user_id": "testuser", "passcode": "pass1234"})
    response = client.post("/logout", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
