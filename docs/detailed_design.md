# 詳細設計書（PC管理システム）

## 1. 文書情報
- 文書名: 詳細設計書
- 対象システム: PC管理システム（FastAPI + Jinja2）
- 作成日: 2026-02-05
- 目的: 画面・API・データ・処理・例外・運用までを網羅し、実装と運用の基準を明確化する。

---

## 2. システム構成
### 2.1 アーキテクチャ
- 種別: サーバレンダリングWebアプリ（FastAPI + Jinja2）
- 画面: Jinja2テンプレート
- DB: MySQL 8.4（開発/テストはSQLite許容）
- ORM: SQLAlchemy
- 認証: セッション（Cookie）
- ログ: Python logging（コンソール + ローテーションファイル）

### 2.2 モジュール構成
- app/main.py: FastAPI起動、ミドルウェア、例外ハンドラ、ルーティング登録
- app/config.py: 環境変数読込と設定
- app/db.py: DB接続、Session提供
- app/models.py: ORMモデルとステータス定義
- app/status_rules.py: 状態遷移許可ルール
- app/transition_service.py: 遷移適用・監査ログ
- app/plan_rules.py: 予定整合性チェック
- app/validation.py: 資産/要求の入力検証
- app/security.py: パスコードハッシュ/検証
- app/utils.py: Flashと日時(JST)処理
- app/routes/*: 画面/操作のルーティング
- templates/*: 画面テンプレート
- static/app.css: UIスタイル
- tools/*: 補助スクリプト

---

## 3. 設定・環境
### 3.1 環境変数
- DATABASE_URL: DB接続URL
- SECRET_KEY: セッション署名キー
- LOG_LEVEL: ログレベル

### 3.2 既定値
- DATABASE_URL: sqlite:///./pc_management.db
- SECRET_KEY: change-this-secret
- LOG_LEVEL: INFO

---

## 4. データ設計
### 4.1 テーブル一覧
- users
- pc_assets
- pc_requests
- pc_plans
- pc_status_history

### 4.2 テーブル詳細
#### 4.2.1 users
- id: int PK
- user_id: varchar(64) UNIQUE NOT NULL
- passcode_hash: varchar(255) NOT NULL
- display_name: varchar(128) NOT NULL
- role: enum('ADMIN','USER') NOT NULL
- is_active: boolean NOT NULL
- created_at: datetime NOT NULL
- updated_at: datetime NOT NULL

#### 4.2.2 pc_assets
- id: int PK
- asset_tag: varchar(50) UNIQUE NOT NULL
- serial_no: varchar(128) UNIQUE NULL
- hostname: varchar(63) NULL
- status: enum('INV','READY','USE','RET','IT','DIS','AUD','LOST') NOT NULL
- current_user: varchar(128) NULL
- location: varchar(128) NULL
- request_id: int NULL (pc_requests.id)
- notes: text NULL
- created_at: datetime NOT NULL
- updated_at: datetime NOT NULL

#### 4.2.3 pc_requests
- id: int PK
- status: enum('RQ','OP','RP') NOT NULL
- requester: varchar(128) NULL
- note: text NULL
- asset_id: int NULL (pc_assets.id)
- created_at: datetime NOT NULL
- updated_at: datetime NOT NULL

#### 4.2.4 pc_plans
- id: int PK
- entity_type: varchar(16) NOT NULL (ASSET/REQUEST)
- entity_id: int NOT NULL
- title: varchar(255) NOT NULL
- planned_date: date NULL
- planned_owner: varchar(128) NULL
- plan_status: enum('PLANNED','DONE','CANCELLED') NOT NULL
- actual_date: date NULL
- actual_owner: varchar(128) NULL
- result_note: text NULL
- created_by: varchar(64) NOT NULL
- created_at: datetime NOT NULL
- updated_at: datetime NOT NULL

#### 4.2.5 pc_status_history
- id: int PK
- entity_type: varchar(16) NOT NULL (REQUEST/ASSET)
- entity_id: int NOT NULL
- from_status: varchar(16) NULL
- to_status: varchar(16) NOT NULL
- changed_by: varchar(64) NOT NULL
- reason: varchar(1000) NULL
- ticket_no: varchar(64) NULL
- changed_at: datetime NOT NULL

### 4.3 ステータス定義
- 要求: RQ(要望受付), OP(手配予定), RP(準備予定)
- 資産: INV(未利用在庫), READY(利用準備完了), USE(利用中), RET(回収済), IT(IT部引渡済), DIS(廃棄済), AUD(棚卸差異), LOST(所在不明)
- 予定: PLANNED(予定), DONE(完了), CANCELLED(中止)

---

## 5. 状態遷移設計
### 5.1 要求ステータス遷移
- NR -> RQ
- RQ -> OP
- OP -> RP

### 5.2 資産ステータス遷移
- INV -> READY -> USE -> RET
- RET -> INV / IT / DIS
- IT -> READY
- 監査遷移: (INV/READY/USE/RET/IT/DIS/LOST) -> AUD
- 監査復帰: AUD -> USE/INV/RET/IT/DIS/LOST
- 紛失復帰: LOST -> USE/RET/IT/DIS
- 新規登録時許可: INV/USE/RET/IT/DIS/LOST

### 5.3 遷移エラー
- 不許可遷移は 409 を返し、画面にエラー表示
- 監査ログへ残す（pc_status_history）

---

## 6. バリデーション設計
### 6.1 資産
- asset_tag: 必須、50文字以内
- hostname: 63文字以内
- notes: 5000文字以内
- status=USE の場合 current_user 必須

### 6.2 要求
- requester: 128文字以内
- note: 1000文字以内

### 6.3 予定
- title: 必須
- plan_status=DONE: actual_date 必須
- plan_status=PLANNED/CANCELLED: actual_date/actual_owner 入力禁止

---

## 7. 画面設計
### 7.1 共通
- ナビゲーション: ダッシュボード/資産一覧/要求一覧/期限超過予定
- フラッシュ: success/warning/error を画面上部に表示

### 7.2 ログイン
- 入力: user_id, passcode
- 認証成功: /dashboard へ遷移
- 認証失敗: エラーフラッシュ

### 7.3 ダッシュボード
- 資産/要求/予定のステータス集計
- 期限超過予定件数

### 7.4 資産一覧
- 検索条件: 状態/資産番号・シリアル/利用者/拠点/予定担当/期限超過のみ/今日のみ/次予定表示件数(1-3)
- 表示: 次予定(直近N件) + 期限超過/今日バッジ
- 一覧操作: 予定追加、次予定完了（簡易フォーム）

### 7.5 資産詳細
- 資産情報表示
- 状態遷移（許可遷移のみ）
- 予定一覧: 追加/完了/中止/編集
- 状態履歴

### 7.6 要求一覧
- ステータス/申請者で検索
- 一覧で状態遷移

### 7.7 要求詳細
- 要求情報表示
- 状態履歴

### 7.8 予定（期限超過）
- 期限超過予定の一覧と完了操作
- 予定登録/編集/削除

---

## 8. ルーティング/API設計
### 8.1 認証
- GET /login: ログイン画面
- POST /login: 認証処理
- POST /logout: ログアウト

### 8.2 ダッシュボード
- GET /dashboard: 集計表示

### 8.3 資産
- GET /assets: 一覧/検索
- GET /assets/new: 新規登録画面
- POST /assets: 登録
- GET /assets/{id}: 詳細
- GET /assets/{id}/edit: 編集画面
- POST /assets/{id}/edit: 更新
- POST /assets/{id}/delete: 削除
- POST /assets/{id}/transition: 状態遷移
- POST /assets/{id}/plans: 予定追加
- POST /assets/{id}/plans/{plan_id}/done: 予定完了
- POST /assets/{id}/plans/{plan_id}/cancel: 予定中止
- POST /assets/import: CSVインポート（未実装）

### 8.4 要求
- GET /requests: 一覧/検索
- GET /requests/new: 新規登録画面
- POST /requests: 登録
- GET /requests/{id}: 詳細
- GET /requests/{id}/edit: 編集画面
- POST /requests/{id}/edit: 更新
- POST /requests/{id}/delete: 削除
- POST /requests/{id}/transition: 状態遷移

### 8.5 予定
- GET /plans/overdue: 期限超過予定一覧
- GET /plans/new: 新規登録画面
- POST /plans: 登録
- GET /plans/{id}: 詳細
- GET /plans/{id}/edit: 編集画面
- POST /plans/{id}/edit: 更新
- POST /plans/{id}/delete: 削除
- POST /plans/{id}/done: 期限超過予定の完了

---

## 9. 処理フロー
### 9.1 資産一覧
1. 検索条件の受け取り
2. pc_assetsを200件まで取得
3. pc_plansをまとめて取得
4. 次予定/期限超過/今日予定を計算
5. 画面表示

### 9.2 資産状態遷移
1. 現状態と遷移先を取得
2. status_rulesで許可判定
3. 許可: 更新 + pc_status_history登録
4. 不許可: 409 + エラーフラッシュ

### 9.3 予定追加/完了/中止
- 追加: 予定日必須、整合チェック → 登録
- 完了: 実績日必須、整合チェック → 更新
- 中止: 実績情報をクリア → 更新

### 9.4 要求登録/更新
- 申請者/メモの長さチェック
- asset_idは数字のみ許可

---

## 10. 例外・エラーハンドリング
- DB例外: 500で固定メッセージ
- 不許可遷移: 409 + 画面でエラー表示
- 重複/外部キー違反: フラッシュで入力エラー表示

---

## 11. ログ設計
- HTTPアクセスログ: パス/メソッド/ステータス/レイテンシ
- 予定整合チェック: 成否ログ
- 状態遷移: 許可/不許可ログ
- 例外: スタックトレース
- 出力先: console + logs/app.log（ローテーション）

---

## 12. 認証・権限
- セッションでログイン維持
- 未ログインは /login へリダイレクト
- 役割(role)は保持するが機能制限は未実装

---

## 13. 非機能
- 一覧表示は200件まで
- 文字数制限はバリデーションで制御
- JST表示: テンプレートフィルタformat_jst

---

## 14. 運用
- .envで環境差分を吸収
- decision_log.mdへ変更記録
- 重要データはDBバックアップ対象
- ログはローテーション、容量監視推奨

---

## 15. 未実装・留意点
- CSVインポート機能は未実装
- 権限別のUI制御は未実装
- 監査票番号(ticket_no)の入力UI未実装
