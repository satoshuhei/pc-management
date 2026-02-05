# 基本設計書（PC管理システム）

## 1. 文書情報
- 文書名: 基本設計書
- 対象システム: PC管理システム（FastAPI + Jinja）
- 作成日: 2026-02-05
- 目的: システムの全体像、機能・画面・データ・処理・非機能を網羅し、共通理解を形成する。

---

## 2. システム概要
Excel台帳で運用しているPC管理をWebシステムに移行する。資産・要求・予定/実績・状態遷移・監査ログを一元管理し、一覧で状況把握、詳細で確実な登録/編集を行う。

### 2.1 主要コンセプト
- **一覧で回す**: 素早い検索、次の予定の把握、最小操作。
- **詳細で整える**: 予定の追加/完了/中止/編集、状態遷移、履歴確認。
- **状態遷移の厳格化**: PlantUML定義に準拠し、許可遷移のみ通す。

---

## 3. 技術構成
- バックエンド: FastAPI
- テンプレート: Jinja2（サーバレンダリング）
- ORM: SQLAlchemy
- DB: MySQL 8.4（開発/テストはSQLiteを許容）
- 認証: Cookieセッション
- ログ: Python logging（コンソール + logs/app.log）
- テスト: pytest

---

## 4. データ構成
### 4.1 ER概略
- users
- pc_assets
- pc_requests
- pc_plans
- pc_status_history

### 4.2 テーブル定義（要旨）
#### users
- id (PK)
- user_id (UNIQUE)
- passcode_hash
- display_name
- role (ADMIN/USER)
- is_active
- created_at, updated_at

#### pc_assets
- id (PK)
- asset_tag (UNIQUE)
- serial_no (UNIQUE/NULL可)
- hostname
- status
- current_user
- location
- request_id (FK pc_requests.id)
- notes
- created_at, updated_at

#### pc_requests
- id (PK)
- status
- requester
- note
- asset_id (FK pc_assets.id)
- created_at, updated_at

#### pc_plans
- id (PK)
- entity_type (ASSET/REQUEST)
- entity_id
- title
- planned_date
- planned_owner
- plan_status (PLANNED/DONE/CANCELLED)
- actual_date
- actual_owner
- result_note
- created_by
- created_at, updated_at

#### pc_status_history
- id (PK)
- entity_type (REQUEST/ASSET)
- entity_id
- from_status
- to_status
- changed_by
- reason
- ticket_no
- changed_at

---

## 5. 状態管理
### 5.1 要求フェーズ
- NR: 台帳行なし（レコードなし）
- RQ: 要望受付
- OP: 手配予定
- RP: 準備予定

### 5.2 資産フェーズ
- INV: 未利用在庫
- READY: 利用準備完了
- USE: 利用中
- RET: 回収済
- IT: IT部引渡済
- DIS: 廃棄済
- AUD: 棚卸差異
- LOST: 所在不明

### 5.3 遷移ルール
- PlantUMLに準拠した許可遷移のみ実行。
- 不許可遷移は 409 を返し、画面にエラー表示。

---

## 6. 予定管理
### 6.1 データ方針
- 実績専用テーブルは作らず、pc_plansのactual_*に保持。

### 6.2 予定の整合ルール
- DONE時: actual_date 必須
- PLANNED/CANCELLED時: actual_* はNULL

### 6.3 次予定の定義
- plan_status=PLANNED かつ planned_date最小の1件（一覧表示は最大N件）
- planned_dateがNULLは次予定判定から除外

### 6.4 予定状況バッジ
- 期限超過あり: PLANNED で planned_date < 今日
- 今日の予定あり: PLANNED で planned_date = 今日

---

## 7. 画面構成
### 7.1 共通
- ナビゲーション: ダッシュボード/資産一覧/要求一覧/期限超過予定
- 操作ログ（flash）: 成功✅/注意⚠/失敗❌

### 7.2 ダッシュボード
- 2x2グリッド
- 左上: 資産ステータス
- 左下: 要求ステータス
- 右上: 予定ステータス
- 右下: 期限超過

### 7.3 資産一覧（/assets）
- **検索**: 状態/資産番号・シリアル/利用者/拠点/予定担当/期限超過のみ/今日のみ
- **表示列**:
  - 資産番号
  - 資産名（ホスト名）
  - 状態（日本語 + コード）
  - 利用者
  - 拠点
  - 次の予定（直近N件）
  - 予定状況（バッジ）
  - 操作（詳細/予定追加/次予定完了）
- **操作**:
  - 予定追加（簡易フォーム）
  - 次予定完了（簡易フォーム）
- **一覧で行わない**: 予定編集/並び替え/実績詳細

### 7.4 資産詳細（/assets/{id}）
- 資産基本情報
- 状態遷移（許可遷移のみ）
- 予定一覧（PLANNED/DONE/CANCELLED）
- 予定追加/完了/中止/編集
- 状態遷移履歴

### 7.5 要求一覧（/requests）
- 要求の一覧表示
- 状態遷移
- 詳細画面で内容確認

### 7.6 期限超過予定（/plans/overdue）
- 期限超過予定の一覧
- 完了操作

---

## 8. 主要機能
- 認証（ログイン/ログアウト）
- 資産 CRUD
- 要求 CRUD
- 予定 CRUD
- 状態遷移（厳格制御）
- 操作ログ（画面/サーバログ）
- バリデーション（入力必須、長さ制限、整合性）

---

## 9. バリデーション
- 共通: 前後空白トリム、必須、長さ制限
- 資産: asset_tag必須、hostname長さ、USE時current_user必須
- 予定: title必須、DONE時actual_date必須、未完了時actual_*禁止

---

## 10. ログ設計
### 10.1 サーバログ
- HTTP request/response
- 状態遷移結果
- 予定整合処理
- DB例外

### 10.2 画面ログ（flash）
- 成功/注意/失敗を画面上部に表示

---

## 11. 非機能要件
- セッションベース認証
- DB例外の安全なハンドリング
- レイアウト: Redmine風UI
- レスポンス: 200件程度まで一覧表示（現状）

---

## 12. テスト方針
- 状態遷移ルール
- 予定整合
- 認証
- 一覧/詳細の描画
- 次予定選定/バッジ判定

---

## 13. 運用ルール
- 変更時はテスト追加→実行→OK→コミット
- decision_log.md に指示/対応/テスト結果を記録

---

## 14. 将来拡張
- 予定の検索強化
- 次予定キャッシュ列/ビュー
- 予定操作ログの履歴化
- 権限管理の強化
