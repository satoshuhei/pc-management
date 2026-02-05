from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone, date
from app.db import SessionLocal
from app.models import User, UserRole, PcAsset, AssetStatus, PcRequest, RequestStatus, PcPlan, PlanStatus
from app.security import hash_passcode

# サンプルユーザ作成
USER_ID = "shuiei"
PASS = "pass"

# サンプルデータ生成用定数
ASSET_STATUSES = list(AssetStatus)
REQUEST_STATUSES = list(RequestStatus)
PLAN_STATUSES = list(PlanStatus)


def create_sample_user(session):
    user = session.query(User).filter_by(user_id=USER_ID).first()
    if not user:
        user = User(
            user_id=USER_ID,
            passcode_hash=hash_passcode(PASS),
            display_name="サンプルユーザ",
            role=UserRole.USER,
            is_active=True,
        )
        session.add(user)
        session.commit()
    return user


def create_sample_assets(session, count_per_status=10):
    assets = []
    for status in ASSET_STATUSES:
        for i in range(count_per_status):
            asset_tag = f"AST-{status.value}-{i:02}"
            serial_no = f"SN-{status.value}-{i:04}"
            exists = (
                session.query(PcAsset)
                .filter(
                    (PcAsset.asset_tag == asset_tag) | (PcAsset.serial_no == serial_no)
                )
                .first()
            )
            if exists:
                continue
            asset = PcAsset(
                asset_tag=asset_tag,
                serial_no=serial_no,
                hostname=f"host-{status.value.lower()}-{i:02}",
                status=status,
                current_user=None,
                location=f"拠点{random.randint(1,5)}",
                notes=f"{status.value}状態のサンプル資産",
            )
            session.add(asset)
            assets.append(asset)
    session.commit()
    if assets:
        return assets
    return session.query(PcAsset).all()


def create_sample_requests(session, assets, count_per_status=10):
    requests = []
    if not assets:
        return requests
    for status in REQUEST_STATUSES:
        for i in range(count_per_status):
            asset = random.choice(assets)
            req = PcRequest(
                status=status,
                requester=f"user{random.randint(1,5)}",
                note=f"{status.value}状態のサンプルリクエスト",
                asset_id=asset.id,
            )
            session.add(req)
            requests.append(req)
    session.commit()
    return requests


def create_sample_plans(session, assets, count_per_status=10):
    plans = []
    if not assets:
        return plans
    for status in PLAN_STATUSES:
        for i in range(count_per_status):
            asset = random.choice(assets)
            plan = PcPlan(
                entity_type="ASSET",
                entity_id=asset.id,
                title=f"{status.value}計画サンプル{i+1}",
                planned_date=date.today() + timedelta(days=random.randint(1, 30)),
                planned_owner=f"owner{random.randint(1,5)}",
                plan_status=status,
                actual_date=None,
                actual_owner=None,
                result_note=f"{status.value}の結果ノート",
                created_by=USER_ID,
            )
            session.add(plan)
            plans.append(plan)
    session.commit()
    return plans


def main():
    from app.db import engine, Base
    # テーブル自動生成
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        user = create_sample_user(session)
        assets = create_sample_assets(session)
        requests = create_sample_requests(session, assets)
        plans = create_sample_plans(session, assets)
        print("サンプルデータ作成完了")
    finally:
        session.close()

if __name__ == "__main__":
    main()
