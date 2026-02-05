from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import AssetStatus, PcAsset, PcPlan, PlanStatus, User, UserRole
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

    planned = PcPlan(
        entity_type="ASSET",
        entity_id=asset.id,
        title="次予定",
        planned_date=date.today() + timedelta(days=1),
        planned_owner="担当者A",
        plan_status=PlanStatus.PLANNED,
        actual_date=None,
        actual_owner=None,
        result_note=None,
        created_by="testuser",
    )
    db.add(planned)
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
    client.cookies.update(login.cookies)
    return client


def test_asset_plan_add():
    client = _login_client()
    res = client.post(
        "/assets/1/plans",
        data={
            "title": "追加予定",
            "planned_date": date.today().isoformat(),
            "planned_owner": "担当者B",
        },
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert "予定を追加しました。" in res.text
    app.dependency_overrides.clear()


def test_asset_plan_done():
    client = _login_client()
    db = TestingSessionLocal()
    plan = db.query(PcPlan).first()
    db.close()
    res = client.post(
        f"/assets/1/plans/{plan.id}/done",
        data={"actual_date": date.today().isoformat(), "result_note": "完了"},
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert "次の予定を完了しました。" in res.text
    app.dependency_overrides.clear()
