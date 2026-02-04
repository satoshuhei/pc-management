# pc-management

FastAPI + Jinja2 で動くPC管理システムのベースです。

## 1. セットアップ（ローカル）

1) 依存関係のインストール

```
pip install -r requirements.txt
```

2) .env の作成（.env.example をコピー）

3) MySQL 8.4 に DB を作成

4) 起動

```
uvicorn app.main:app --reload
```

## 2. .env の例

```
DATABASE_URL=mysql+mysqlconnector://pc_user:pc_pass@localhost:3306/pc_management
SECRET_KEY=change-this-secret
LOG_LEVEL=INFO
```

## 3. 管理者用パスコードハッシュ

```
python -m tools.hash_passcode "plainpass"
```

## 4. DB 初期DDL（抜粋）

```sql
CREATE TABLE users (
	id BIGINT AUTO_INCREMENT PRIMARY KEY,
	user_id VARCHAR(64) NOT NULL UNIQUE,
	passcode_hash VARCHAR(255) NOT NULL,
	display_name VARCHAR(128) NOT NULL,
	role ENUM('ADMIN','USER') NOT NULL DEFAULT 'USER',
	is_active BOOLEAN NOT NULL DEFAULT 1,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL
);

CREATE TABLE pc_requests (
	id BIGINT AUTO_INCREMENT PRIMARY KEY,
	status ENUM('RQ','OP','RP') NOT NULL,
	requester VARCHAR(128),
	note TEXT,
	asset_id BIGINT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL
);

CREATE TABLE pc_assets (
	id BIGINT AUTO_INCREMENT PRIMARY KEY,
	asset_tag VARCHAR(50) NOT NULL UNIQUE,
	serial_no VARCHAR(128) UNIQUE,
	hostname VARCHAR(63),
	status ENUM('INV','READY','USE','RET','IT','DIS','AUD','LOST') NOT NULL,
	current_user VARCHAR(128),
	location VARCHAR(128),
	request_id BIGINT NULL,
	notes TEXT,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL
);

CREATE TABLE pc_status_history (
	id BIGINT AUTO_INCREMENT PRIMARY KEY,
	entity_type VARCHAR(16) NOT NULL,
	entity_id BIGINT NOT NULL,
	from_status VARCHAR(16),
	to_status VARCHAR(16) NOT NULL,
	changed_by VARCHAR(64) NOT NULL,
	reason VARCHAR(1000),
	ticket_no VARCHAR(64),
	changed_at DATETIME NOT NULL
);

CREATE TABLE pc_plans (
	id BIGINT AUTO_INCREMENT PRIMARY KEY,
	entity_type VARCHAR(16) NOT NULL,
	entity_id BIGINT NOT NULL,
	title VARCHAR(255) NOT NULL,
	planned_date DATE,
	planned_owner VARCHAR(128),
	plan_status ENUM('PLANNED','DONE','CANCELLED') NOT NULL,
	actual_date DATE,
	actual_owner VARCHAR(128),
	result_note TEXT,
	created_by VARCHAR(64) NOT NULL,
	created_at DATETIME NOT NULL,
	updated_at DATETIME NOT NULL
);
```

## 5. テスト

```
pytest
```