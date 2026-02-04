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


def _seed_entities():
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
    plan = PcPlan(
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
    db.add_all([req, plan])
    db.commit()
    db.close()


def _login_client() -> TestClient:
    app.dependency_overrides[get_db] = _override_db
    _seed_entities()
    client = TestClient(app)
    login = client.post(
        "/login",
        data={"user_id": "testuser", "passcode": "pass1234"},
        follow_redirects=False,
    )
    assert login.status_code == 303
    client.cookies.update(login.cookies)
    return client


def test_asset_transition_allowed():
    client = _login_client()
    db = TestingSessionLocal()
    asset = db.query(PcAsset).first()
    db.close()

    res = client.post(
        f"/assets/{asset.id}/transition",
        data={"to_status": "READY", "reason": "テスト"},
        follow_redirects=False,
    )
    assert res.status_code == 303

    db = TestingSessionLocal()
    updated = db.query(PcAsset).filter(PcAsset.id == asset.id).first()
    db.close()
    assert updated.status == AssetStatus.READY
    app.dependency_overrides.clear()


def test_asset_transition_denied():
    client = _login_client()
    db = TestingSessionLocal()
    asset = db.query(PcAsset).first()
    db.close()

    res = client.post(
        f"/assets/{asset.id}/transition",
        data={"to_status": "USE"},
        follow_redirects=False,
    )
    assert res.status_code == 409
    app.dependency_overrides.clear()


def test_request_transition_allowed():
    client = _login_client()
    db = TestingSessionLocal()
    req = db.query(PcRequest).first()
    db.close()

    res = client.post(
        f"/requests/{req.id}/transition",
        data={"to_status": "OP", "reason": "テスト"},
        follow_redirects=False,
    )
    assert res.status_code == 303

    db = TestingSessionLocal()
    updated = db.query(PcRequest).filter(PcRequest.id == req.id).first()
    db.close()
    assert updated.status == RequestStatus.OP
    app.dependency_overrides.clear()


def test_plan_done_updates_actuals():
    client = _login_client()
    db = TestingSessionLocal()
    plan = db.query(PcPlan).first()
    db.close()

    res = client.post(
        f"/plans/{plan.id}/done",
        data={"result_note": "完了メモ"},
        follow_redirects=False,
    )
    assert res.status_code == 303

    db = TestingSessionLocal()
    updated = db.query(PcPlan).filter(PcPlan.id == plan.id).first()
    db.close()
    assert updated.plan_status == PlanStatus.DONE
    assert updated.actual_date is not None
    assert updated.actual_owner == "testuser"
    app.dependency_overrides.clear()


def test_assets_import_shows_flash():
    client = _login_client()
    res = client.post(
        "/assets/import",
        files={"file": ("sample.csv", b"id,tag\n1,AST-1\n", "text/csv")},
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert "インポート機能は準備中です。" in res.text
    app.dependency_overrides.clear()
