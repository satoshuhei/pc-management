
import os
import sys
import tempfile
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + '/../'))
from app.db import Base, SessionLocal, engine
from app.models import User
from tools.create_sample_data import main as create_sample_data_main

def test_sample_user_created():
    # テスト用DBファイルを一時作成
    db_fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(db_fd)
    os.environ['DATABASE_URL'] = f'sqlite:///{db_path}'
    try:
        # テーブル作成＆サンプルデータ投入
        Base.metadata.create_all(bind=engine)
        create_sample_data_main()
        session = SessionLocal()
        user = session.query(User).filter_by(user_id="shuiei").first()
        assert user is not None
        assert user.user_id == "shuiei"
        session.close()
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)
