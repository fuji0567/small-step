# API サーバー

- 索引: [../architecture.md](../architecture.md)

## 園別試用モード

プロコン用の処理表示は `POST /recorder/sessions` の厳密な真偽値 `demo_trace_requested`（既定false）で
明示同意した試用録音に限定します。DBへ本文を保存せず、内容を含まない暗号化済み一時同意ファイルを使います。
`GET /recorder/sessions/{id}/demo` は本人ログイン・録音所有者・現在の園の試用モードを毎回確認し、
専用キーで復号した5分以内の結果だけを `Cache-Control: no-store, private` で返します。
管理者への例外許可やdevelopment認証の素通しはありません。通常のセッションGETや一覧には内容を混ぜません。
公開認証設定には有効フラグだけを追加し、暗号化キーやLLM接続情報は公開しません。

`POST /schools` は `trial_mode=true` で作成します。`SchoolRead` と `GET /auth/me` は現在の園の
`trial_mode`、記録と録音セッションの応答は永久保持する `is_trial` を返します。
`PATCH /schools/{id}/trial-mode` はその園の先生管理者限定です。本番への切り替えは
`{"trial_mode": false, "delivery_confirmed": true}` が必須です。未確認や文字列のフラグは422です。
変更は本文や秘密情報を含まない `school_trial_mode_changed` 操作履歴を残します。

試用記録の承認は記録を `approved`、通知を終端状態 `trial` にし、送信先は保持しません。
試用通知は配信キューから除外し、再送・日時変更・送信済み変更・Notion同期を409で拒否します。
LINEワーカーもAPIを経由せず同じDBの試用フラグを確認します。詳細は [試用導入手順](../school-trial-runbook.md)。

FastAPI 製の単一プロセスです。全エンドポイントは `/api/v1` 配下にあり、
先生用・保護者用の静的アプリも同じプロセスから配信します。

---

## アプリケーションの組み立て

`app/main.py` の `create_app()` が組み立てを一手に引き受けます。

```
create_app(settings)
  ├ create_database_engine(database_url)
  ├ lifespan
  │   └ SQLite のときだけ prepare_database() で移行を適用
  ├ app.state.settings / engine / session_factory
  ├ middleware: /_app/*・/rec/assets/* は immutable、HTML は no-cache
  ├ include_router(router)            … app/api/routes.py（prefix /api/v1）
  └ app/frontend_dist が揃っている場合だけ
      ├ mount("/_app",     StaticFiles(frontend_dist/_app))
      ├ mount("/guardian", StaticFiles(frontend_dist/guardian, html=True))
      ├ GET /teacher         → /teacher/ へ redirect
      └ GET /teacher/{path}  → frontend_dist/200.html
  └ RECORDER_ENABLED=true かつ app/recorder_dist が揃っている場合
      └ mount("/rec", StaticFiles(recorder_dist, html=True))
```

- 設定を引数で差し替えられるため、テストは本番用の環境変数を読まずにアプリを組み立てられます。
- SQLite のときだけ起動時に移行を適用します。PostgreSQL では Alembic を明示的に実行する運用です
  （[data-model.md](data-model.md) を参照）。
- `app/frontend_dist/` がない場合、開発では UI をマウントせずに API だけで起動し、`APP_ENV=production` では起動を止めます。
  生成物が不完全な場合は環境を問わず起動を止めます。配信契約の詳細は [frontend.md](frontend.md) の「配信」を参照してください。
- 録音PWAは `RECORDER_ENABLED=false` が既定です。無効時は `app/recorder_dist/` の有無にかかわらず配信せず、
  有効な本番環境だけ完全な録音ビルドを必須にします。

---

## ファイル構成

| ファイル | 役割 |
| --- | --- |
| `app/main.py` | アプリ生成、静的マウント、ライフサイクル |
| `app/api/routes.py` | 全エンドポイント（単一ルーター） |
| `app/api/dependencies.py` | DB セッション、認証、園スコープ、管理者判定 |
| `app/schemas.py` | Pydantic の入出力モデル |
| `app/models.py` | SQLAlchemy のテーブル定義 |
| `app/database.py` | エンジンとセッションファクトリ |
| `app/database_migrations.py` | SQLite 向けの移行適用 |
| `app/config.py` | 環境変数の読み込みと本番構成の検証 |

---

## エンドポイントの分類

`POST /teachers/{id}/invite` は同じ園の管理者だけが使う招待送信です。
有効・未連携の先生に限定し、開発モードや送信未設定は503、対象状態不一致は409、再送間隔は429です。
成功は通常の先生メタデータと `invitation_sent_at` を返し、メール・トークンを含むSupabase応答は返しません。
`GET /auth/config` の `teacher_invitations_enabled` は公開可否フラグだけです。

タグごとのエンドポイント数です（`/api/v1` 配下、合計 70 本）。

| タグ | 数 | 代表的なエンドポイント |
| --- | --- | --- |
| `records` | 8 | `GET /records/{id}`, `PATCH /records/{id}/assignee`, `POST /records/{id}/approve`, `POST /records/manual` |
| `notifications` | 6 | `GET /notifications`, `POST /notifications/{id}/retry`, `PATCH /notifications/{id}/schedule` |
| `children` | 6 | `POST /children`, `POST /children/{id}/archive`, `DELETE /children/{id}/guardian-line-link` |
| `teachers` | 6 | `GET /teachers`, `POST /teachers/{id}/invite`, `PATCH /teachers/{id}/role`, `POST /teachers/{id}/disable` |
| `auth` | 5 | `GET /auth/config`, `GET /auth/me`, `POST /auth/link-teacher`, `POST /auth/bootstrap/teacher` |
| `edge devices` | 4 | `POST /edge-devices`, `POST /edge-devices/{id}/rotate-key` |
| `voice consent` | 3 | `GET /voice-consent/me`, `POST /voice-consent/me/revoke` |
| `voiceprint` | 5 | `GET /voiceprint/me`, `POST /voiceprint/me/enroll`, `POST /voiceprint/me/verify` |
| `schools` | 3 | `POST /schools`, `PATCH /schools/{id}/digest-time` |
| `line` | 3 | `POST /line/webhook`, `POST /line/link-invitations` |
| `guardian archive` | 3 | `POST /guardian-archive-links`, `GET /guardian/archive` |
| `edge` | 3 | `POST /edge/records`, `POST /edge/heartbeat`, `GET /edge/me` |
| `cloud audio` | 3 | `POST /edge/audio-jobs`, `GET /audio-jobs` |
| `recorder` | 6 | `POST /recorder/sessions`, `PUT /recorder/sessions/{id}/segments/{sequence}`, `POST /recorder/sessions/{id}/finalize` |
| `system` | 3 | `GET /health`, `GET /readiness`, `GET /navigation-badges` |
| `audit` | 2 | `GET /audit-events`, `GET /audit-events/export.csv` |
| `notion` | 1 | `POST /records/{id}/notion-sync` |

`POST /voiceprint/me/enroll` は同名の `audio` フィールドを3件受け取り、`POST /voiceprint/me/verify` は1件だけ受け取ります。声紋ジョブの応答は品質不合格時に理由と1始まりの録音番号を返しますが、保存先、元音声、特徴量は返しません。

`POST /voice-consent/me` の `allows_recorder_identification` は既定falseの追加同意です。
falseでの更新は既存の担当候補も削除します。`GET /records/{record_id}/voiceprint-suggestion` は
通常の記録と同じ閲覧権限を検証し、機能停止・未実施は `disabled`、不明は `unidentified`、
現在も同意・声紋・先生が有効な同じ園の一致だけを `candidate` と先生ID・表示名で返します。
特徴量・類似度は返しません。変更操作は従来の管理者限定 `PATCH /records/{record_id}/assignee` のままです。

`POST /children` と `PATCH /children/{id}` は管理者だけが `recording_names`（敬称なし、2〜40文字、
最大5件の呼び名・読み方）を設定できます。PATCHで省略した場合は保持し、空配列で消去します。
`GET /records/{id}/child-suggestion` は通常の記録と同じ閲覧権限を確認し、機能有効・未承認・未選択・
同じ園の在籍園児に限り `candidate` と園児ID・表示名を返し、それ以外は `unidentified` です。
呼び名や生の文字起こし、参照対応表は応答へ含めません。通常のRecordReadに候補IDは追加しません。
録音由来の `POST /records/{id}/approve` は `child_confirmed=true` を必須とし、園児は既存の
在籍・園スコープ検証を通した明示選択だけを使います。候補を配信先へ自動昇格させません。

利用者別の入口:

- **先生用アプリ** … `auth` / `records` / `notifications` / `children` / `teachers` / `schools` / `edge devices` / `audit` / `voice consent` / `voiceprint` / `recorder`
- **録音端末** … `edge` / `cloud audio`（端末 APIキー認証）
- **LINE** … `line`（Webhook）
- **保護者** … `guardian archive` の `GET /guardian/archive` のみ

GPU ワーカー（`process_cloud_audio_jobs.py`、通常音声と任意の声紋ジョブ）と LINE 送信ワーカー（`send_pending_line_notifications.py`）は
API を経由せず、API と同じデータベースを直接読み書きします。`GET /notifications/ready` と
`POST /notifications/{id}/mark-sent` は先生管理者の Bearer 認証が必要なエンドポイントで、同梱の LINE 送信ワーカーは使いません。

### 録音セッションAPI

`/recorder/sessions` 以下は既存の先生Bearer認証を使い、園と録音者をサーバー側で決定します。一般の先生は
自分の一覧だけを取得し、先生管理者は園全体の安全な状態一覧を取得できます。単一セッションの取得、分割音声の送信、
確定、破棄は先生管理者を含め録音者本人だけに許可します。

分割音声は0始まりの連番、実録音時間、SHA-256を伴うMP4/AACまたはWebM/Opusです。同じ連番・同じ内容の再送は成功し、
内容が異なる場合は409にします。`finalize` は欠番がなく累計60分以内であることを検証して202を返し、状態を `queued` にします。
極端な細分化による保管件数の増加を防ぐため、区間数は最大録音分数×60（既定3600区間）に制限します。
音声本体と元ファイル名はDBへ保存せず、ランダム名で `RECORDER_SESSION_DIR` へ原子的に保存します。

確定後は既存GPUワーカーが処理します。一覧・詳細には `processed_segment_count`（処理を終えた区間数、失敗含む）、
`failed_segment_count`、`record_id`、`audio_processing_incomplete` を返します。内部のclaim tokenや保存キーは返しません。
通常の記録APIにも `audio_processing_incomplete` を返し、部分失敗した録音を承認前に確認できるようにします。
録音有効時のreadinessは通常音声と録音処理の両方の生存確認を要求します。

---

## ナビゲーションバッジ集計

`GET /navigation-badges?school_id=<園ID>` は、先生用ナビゲーションに必要な件数だけを 1 回で返します。
Bearer token による先生認証と `assert_school_access` を必須とし、一覧 API の page size や取得上限には
依存せず、データベース上で `COUNT` します。

```json
{
  "pending_review_records": 3,
  "notification_attention": 1,
  "failed_audio_jobs": 0,
  "invitations_not_issued": 4,
  "readiness_issues": 0
}
```

| フィールド | 集計条件 | 一般の先生 | 先生管理者 |
| --- | --- | --- | --- |
| `pending_review_records` | `pending_review` の日誌 | 自分が担当する日誌 | 園全体 |
| `notification_attention` | `failed` または `waiting_guardian_link` の通知 | 自分が担当する日誌の通知 | 園全体 |
| `failed_audio_jobs` | `failed` のクラウド音声ジョブ | 自分が開始したジョブ | 園全体 |
| `invitations_not_issued` | 在園中、保護者 LINE 未連携、有効な未使用招待なしの園児 | 常に 0 | 園全体 |
| `readiness_issues` | DB、DB migration、有効時のクラウド音声保存先・LLM 設定の不備 | 常に 0 | 園全体の実行環境 |

`readiness_issues` は画面上で対応が必要な blocking check だけを数えます。任意機能である LINE の未設定は
含めません。レスポンスは非負整数だけで、園児名、日誌本文、LINE ID、token、設定値などは返しません。

---

## 依存性注入

`app/api/dependencies.py` が横断的な関心事をまとめています。

| 依存 | 役割 |
| --- | --- |
| `get_db` | リクエストごとの SQLAlchemy セッション。終了時に必ずクローズ |
| `get_authenticated_user` | `Authorization: Bearer` から Supabase のユーザーを解決 |
| `get_current_teacher` | 認証ユーザーに紐づく有効な `teachers` 行を解決 |
| `get_current_edge_device` | 端末 APIキーから `edge_devices` 行を解決 |
| `assert_school_access` | 操作対象が自分の園かを検証 |
| `assert_school_admin` | `school_admin` 限定の操作かを検証 |
| `is_bootstrap_admin` | 初回の管理者登録を許可してよいユーザーかを判定 |

園スコープの検証は各ハンドラの冒頭で明示的に呼びます。
ミドルウェアに隠さないことで、「どのエンドポイントがどこまで許すか」をコード上で追えるようにしています。
詳細は [auth.md](auth.md) を参照してください。

---

## 設定

`app/config.py` の `Settings`（`pydantic-settings`）が環境変数または `.env` を読み込みます。
`get_settings()` は `lru_cache` 付きで、プロセス内で一度だけ評価されます。

設定キーの一覧と既定値は `.env.example` にあります。
`Settings` が読むのはそこにあるキーで、本文で名前を挙げるのは、ふるまいの説明に必要なものだけです。

### 本番構成の検証

`reject_unsafe_production_configuration()` が `APP_ENV=production` のときだけ働き、
次のいずれかに当てはまると起動を止めます。

- `AUTH_MODE` が `supabase` でない
- `SUPABASE_URL` または `SUPABASE_PUBLISHABLE_KEY` が未設定
- `DATABASE_URL` が SQLite
- 保護者アーカイブが有効なのに `GUARDIAN_ARCHIVE_BASE_URL` が HTTPS でない

ローカル開発用の既定値をそのまま公開デプロイに持ち込む事故を、起動時点で防ぐための仕組みです。

---

## エラーの返し方

エラーは `HTTPException` の `detail` に日本語または英語の 1 文で入れます。
フロントエンドがこれをどう表示するかは [frontend.md](frontend.md) の「API 呼び出し」にあります。

よく使う状態コード:

| コード | 用途 |
| --- | --- |
| 401 | Bearer トークンがない、または無効 |
| 403 | 園が違う、`school_admin` でない、機能が無効 |
| 404 | 対象が存在しない、教員として未登録（初回設定へ誘導） |
| 409 | 状態が合わない（レビュー済みの記録を再承認、アーカイブ済みの園児を指定など） |
| 422 | 入力値の検証エラー |
| 503 | 必要な外部設定が未構成（`LINE_CHANNEL_SECRET` 未設定など） |
