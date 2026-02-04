from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import AssetStatus, PcAsset, PcPlan, PcRequest, PlanStatus, RequestStatus, User, UserRole
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


def _seed_user_and_asset():
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
        asset_tag="AST-SEED-01",
        serial_no="SN-SEED-0001",
        hostname="seed-host",
        status=AssetStatus.INV,
        current_user=None,
        location="本社",
        notes="seed",
    )
    db.add_all([user, asset])
    db.commit()
    db.refresh(asset)
    db.close()
    return asset.id


def _login_client() -> TestClient:
    app.dependency_overrides[get_db] = _override_db
    asset_id = _seed_user_and_asset()
    client = TestClient(app)
    login = client.post(
        "/login",
        data={"user_id": "testuser", "passcode": "pass1234"},
        follow_redirects=False,
    )
    assert login.status_code == 303
    client.cookies.update(login.cookies)
    return client, asset_id


def test_asset_create_update_delete():
    client, _ = _login_client()
    create = client.post(
        "/assets",
        data={
            "asset_tag": "AST-CRUD-01",
            "serial_no": "SN-CRUD-01",
            "hostname": "crud-host",
            "status": "INV",
            "current_user": "",
            "location": "拠点A",
            "notes": "登録テスト",
        },
        follow_redirects=False,
    )
    assert create.status_code == 303

    db = TestingSessionLocal()
    asset = db.query(PcAsset).filter(PcAsset.asset_tag == "AST-CRUD-01").first()
    assert asset is not None
    db.close()

    update = client.post(
        f"/assets/{asset.id}/edit",
        data={
            "asset_tag": "AST-CRUD-01A",
            "serial_no": "SN-CRUD-01A",
            "hostname": "crud-host-a",
            "status": "READY",
            "current_user": "",
            "location": "拠点B",
            "notes": "更新テスト",
        },
        follow_redirects=False,
    )
    assert update.status_code == 303

    db = TestingSessionLocal()
    updated = db.query(PcAsset).filter(PcAsset.id == asset.id).first()
    assert updated.asset_tag == "AST-CRUD-01A"
    assert updated.status == AssetStatus.READY
    db.close()

    delete = client.post(f"/assets/{asset.id}/delete", follow_redirects=False)
    assert delete.status_code == 303

    db = TestingSessionLocal()
    deleted = db.query(PcAsset).filter(PcAsset.id == asset.id).first()
    assert deleted is None
    db.close()
    app.dependency_overrides.clear()


def test_request_create_update_delete():
    client, asset_id = _login_client()
    create = client.post(
        "/requests",
        data={
            "requester": "申請者A",
            "note": "登録テスト",
            "asset_id": str(asset_id),
        },
        follow_redirects=False,
    )
    assert create.status_code == 303

    db = TestingSessionLocal()
    req = db.query(PcRequest).filter(PcRequest.requester == "申請者A").first()
    assert req is not None
    db.close()

    update = client.post(
        f"/requests/{req.id}/edit",
        data={
            "requester": "申請者B",
            "note": "更新テスト",
            "asset_id": "",
        },
        follow_redirects=False,
    )
    assert update.status_code == 303

    db = TestingSessionLocal()
    updated = db.query(PcRequest).filter(PcRequest.id == req.id).first()
    assert updated.requester == "申請者B"
    assert updated.asset_id is None
    db.close()

    delete = client.post(f"/requests/{req.id}/delete", follow_redirects=False)
    assert delete.status_code == 303

    db = TestingSessionLocal()
    deleted = db.query(PcRequest).filter(PcRequest.id == req.id).first()
    assert deleted is None
    db.close()
    app.dependency_overrides.clear()


def test_plan_create_update_delete():
    client, asset_id = _login_client()
    create = client.post(
        "/plans",
        data={
            "entity_type": "ASSET",
            "entity_id": str(asset_id),
            "title": "登録予定",
            "planned_date": (date.today() + timedelta(days=1)).isoformat(),
            "planned_owner": "担当者A",
            "plan_status": "PLANNED",
            "actual_date": "",
            "actual_owner": "",
            "result_note": "",
        },
        follow_redirects=False,
    )
    assert create.status_code == 303

    db = TestingSessionLocal()
    plan = db.query(PcPlan).filter(PcPlan.title == "登録予定").first()
    assert plan is not None
    db.close()

    update = client.post(
        f"/plans/{plan.id}/edit",
        data={
            "entity_type": "ASSET",
            "entity_id": str(asset_id),
            "title": "更新予定",
            "planned_date": (date.today() + timedelta(days=2)).isoformat(),
            "planned_owner": "担当者B",
            "plan_status": "DONE",
            "actual_date": date.today().isoformat(),
            "actual_owner": "testuser",
            "result_note": "完了メモ",
        },
        follow_redirects=False,
    )
    assert update.status_code == 303

    db = TestingSessionLocal()
    updated = db.query(PcPlan).filter(PcPlan.id == plan.id).first()
    assert updated.plan_status == PlanStatus.DONE
    assert updated.actual_date is not None
    db.close()

    delete = client.post(f"/plans/{plan.id}/delete", follow_redirects=False)
    assert delete.status_code == 303

    db = TestingSessionLocal()
    deleted = db.query(PcPlan).filter(PcPlan.id == plan.id).first()
    assert deleted is None
    db.close()
    app.dependency_overrides.clear()
