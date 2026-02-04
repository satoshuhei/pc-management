from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import (
    AssetStatus,
    PcAsset,
    PcPlan,
    PcRequest,
    PlanStatus,
    RequestStatus,
    User,
    UserRole,
)
from app.security import hash_passcode

engine = create_engine(
    "sqlite+pysqlite:///:memory:",
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


def _seed_data():
    db = TestingSessionLocal()
    db.query(PcPlan).delete()
    db.query(PcRequest).delete()
    db.query(PcAsset).delete()
    db.query(User).delete()

    user = User(
        user_id="testuser",
        passcode_hash=hash_passcode("pass1234"),
        display_name="テスト太郎",
        role=UserRole.USER,
        is_active=True,
    )
    asset = PcAsset(
        asset_tag="AST-TEST-01",
        serial_no="SN-TEST-0001",
        hostname="host-test-01",
        status=AssetStatus.INV,
        current_user=None,
        location="本社",
        notes="テスト用資産",
    )
    db.add_all([user, asset])
    db.flush()

    req = PcRequest(
        status=RequestStatus.RQ,
        requester="申請者A",
        note="テスト要求",
        asset_id=asset.id,
    )
    overdue_plan = PcPlan(
        entity_type="ASSET",
        entity_id=asset.id,
        title="期限超過テスト",
        planned_date=date.today() - timedelta(days=3),
        planned_owner="担当者A",
        plan_status=PlanStatus.PLANNED,
        actual_date=None,
        actual_owner=None,
        result_note="",
        created_by="testuser",
    )
    db.add_all([req, overdue_plan])
    db.commit()
    db.close()


def _login_client() -> TestClient:
    app.dependency_overrides[get_db] = _override_db
    _seed_data()
    client = TestClient(app)
    login = client.post(
        "/login",
        data={"user_id": "testuser", "passcode": "pass1234"},
        follow_redirects=False,
    )
    assert login.status_code == 303
    assert login.headers["location"] == "/dashboard"
    client.cookies.update(login.cookies)
    return client

@pytest.mark.parametrize("path,title", [
    ("/dashboard", "ダッシュボード"),
    ("/assets", "資産一覧"),
    ("/requests", "要求一覧"),
    ("/plans/overdue", "期限超過予定一覧"),
    ("/assets/1", "資産詳細"),
    ("/requests/1", "要求詳細"),
    ("/plans/1", "予定詳細"),
])
def test_authenticated_pages_accessible(path, title):
    client = _login_client()
    res = client.get(path, follow_redirects=True)
    assert res.status_code == 200, f"{path} should return 200 after login, got {res.status_code}"
    assert title in res.text
    app.dependency_overrides.clear()





def test_protected_pages_redirect():
    with TestClient(app) as client:
        for path in ["/dashboard", "/assets", "/requests", "/plans/overdue"]:
            res = client.get(path, follow_redirects=False)
            assert res.status_code == 303, f"{path} should redirect to /login when not authenticated, got {res.status_code}"
            assert res.headers["location"].startswith("/login")


def test_assets_list_renders_data():
    client = _login_client()
    res = client.get("/assets", follow_redirects=True)
    assert res.status_code == 200
    assert "AST-TEST-01" in res.text
    app.dependency_overrides.clear()


def test_plans_overdue_renders_data():
    client = _login_client()
    res = client.get("/plans/overdue", follow_redirects=True)
    assert res.status_code == 200
    assert "期限超過テスト" in res.text
    app.dependency_overrides.clear()


def test_search_flash_message():
    client = _login_client()
    res = client.get("/assets?status=INV", follow_redirects=True)
    assert res.status_code == 200
    assert "検索条件を適用しました。" in res.text
    app.dependency_overrides.clear()


def test_status_labels_rendered_in_pages():
    client = _login_client()

    res_assets = client.get("/assets", follow_redirects=True)
    assert res_assets.status_code == 200
    assert "未利用在庫" in res_assets.text

    res_requests = client.get("/requests", follow_redirects=True)
    assert res_requests.status_code == 200
    assert "要望受付" in res_requests.text

    res_plans = client.get("/plans/1", follow_redirects=True)
    assert res_plans.status_code == 200
    assert "予定" in res_plans.text

    app.dependency_overrides.clear()


def test_dashboard_layout_quadrants():
    client = _login_client()
    res = client.get("/dashboard", follow_redirects=True)
    assert res.status_code == 200
    assert "dashboard-grid" in res.text
    assert "資産ステータス" in res.text
    assert "要求ステータス" in res.text
    assert "予定ステータス" in res.text
    assert "期限超過" in res.text
    app.dependency_overrides.clear()


def test_assets_layout_redmine_style():
    client = _login_client()
    res = client.get("/assets", follow_redirects=True)
    assert res.status_code == 200
    assert "assets-layout" in res.text
    assert "filter-panel" in res.text
    assert "フィルタ" in res.text
    assert "状態" in res.text
    assert "資産No" in res.text
    assert "チケット一覧" not in res.text
    assert "list-scroll" in res.text
    assert res.text.index("list-scroll") < res.text.index("インポート")
    app.dependency_overrides.clear()
