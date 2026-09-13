# CLAUDE.md

This file provides guidance to coding agents (Claude Code, Codex) when working with code in this repository.
`AGENTS.md` points here, so add or change instructions in this file only.

Small Step（お便りAI）は、幼稚園の会話から「成長の記録」「けがの記録」の候補を作り、
**先生が承認したものだけ** を保護者の LINE へ配信する FastAPI バックエンドです。
UI・ドキュメント・ユーザー向け文言はすべて日本語です。

中心にある制約は **生音声と生の文字起こしを API のデータベースへ持ち込まない** こと。
匿名化は園内のエッジ端末で済ませ、`POST /api/v1/records` には加工済みテキストだけが届きます。
機能を足すときは、まずこの前提を壊していないか確認してください。

## コマンド

Windows では venv の Python を直接呼ぶのが確実です（`.venv/Scripts/python.exe`、現在 3.12.4）。
macOS / Linux は `.venv/bin/python`。

```bash
pip install -e ".[dev]"                                   # 開発用
uvicorn app.main:app --reload                             # http://127.0.0.1:8000
```

- 先生用 <http://127.0.0.1:8000/teacher/> / 保護者用 <http://127.0.0.1:8000/guardian/> / API 仕様 <http://127.0.0.1:8000/docs>
- SQLite なら移行はアプリ起動時に自動適用されるので、事前準備は不要です。

```bash
pytest                                                    # 全テスト
pytest tests/test_api.py::test_growth_record_is_reviewed_and_scheduled   # 単体
pytest -k notion -q                                       # 名前で絞り込み
```

日本語の出力が化けるときは `PYTHONUTF8=1` を付けてください（Windows の cp932 対策）。

```bash
python scripts/prepare_database.py                        # 移行の明示適用（PostgreSQL では必須）
python scripts/check_runtime_readiness.py                 # 不足している設定の洗い出し
python scripts/send_pending_line_notifications.py --dry-run   # 送信対象の確認（実行前に必ず）
python scripts/send_pending_line_notifications.py --watch      # LINE 送信ワーカー（常駐）
python scripts/process_cloud_audio_jobs.py                     # GPU ワーカー（常駐・VRT 用）
python -m app.mcp_server --streamable-http --port 8002          # MCP（ローカル専用）
```

```bash
docker compose up -d --build                                        # api のみ
docker compose -f compose.yaml -f compose.vrt.yaml up -d --build    # migrate + gpu-worker + line-worker
```

音声系の extras（`edge-audio` / `speaker-diarization`）は依存が重いため、
README では別の venv（`.venv313`）へ入れる運用になっています。

## アーキテクチャ

### 入口は 4 経路

認証方式ごとに入口が分かれています（`app/api/dependencies.py`）。

| 経路 | 資格情報 | ヘッダー |
| --- | --- | --- |
| 先生用アプリ | Supabase の access token | `Authorization: Bearer` |
| 録音端末 | 端末ごとの APIキー | `X-Edge-Api-Key` |
| 保護者アーカイブ | 不透明トークン `ssa_...` | `Authorization: Bearer` |
| LINE Webhook | チャネルシークレット署名 | `X-Line-Signature`（生ボディで検証） |

### 記録から配信まで

`records.status` は `pending_review` → `approved` / `rejected` → `dispatched`。
`POST /records/{id}/approve` が `notifications` を 1 行作り（`record_id` に一意制約）、
園児の LINE 連携状況で初期状態が `pending` か `waiting_guardian_link` に分かれます。
配信予定時刻の既定は、けがの記録が即時、成長の記録が園ごとの `digest_time`（既定 17:00 / Asia/Tokyo）。
実際の送信は API ではなく `send_pending_line_notifications.py` が行います。

### 権限

`teacher` と `school_admin` の 2 段階。管理者だけができるのは、園児・先生・端末・園の設定・
監査ログ・通知の再送や取り消し・CSV 書き出しです。
**判定はすべてサーバー側**（`assert_school_admin`）。フロントエンドの非表示は補助でしかありません。

### 単一ルーターと明示的なスコープ検証

全 55 エンドポイントが `app/api/routes.py`（2,300 行超）に入っています。
園スコープと管理者判定は、ミドルウェアに隠さず **各ハンドラの冒頭で明示的に呼ぶ** のがこのリポジトリの慣習です
（`assert_school_access` / `assert_school_admin`）。新しいハンドラでも同じ形を踏襲してください。

### データベースは二重運用

ローカルは SQLite（`./data/otayori.db`、起動時に自動移行）、本番・VRT は PostgreSQL で
`scripts/prepare_database.py` を明示実行（Compose の `migrate` サービス）。
移行ファイルは `migrations/`、Alembic 管理です。SQLite の自動適用は本番では使いません。

### フロントエンドはビルド工程なし

`app/web/`（先生用）と `app/guardian/`（保護者用）を `StaticFiles` でマウントするだけの、
素の HTML/CSS/JS です。Node のツールチェーンは前提にしていません。

- 先生用は単一ページ内で `hidden` を切り替える SPA。URL ルーティングは持たず、`changeView()` が唯一の遷移点。
- アイコンは外部フォントを読まず、`replaceIconPlaceholders()` が起動時にインライン SVG へ置換します。
  **先生用画面は外部ネットワークへ一切リクエストを出しません。**
- トークンは `sessionStorage`（`small-step.access-token`）にのみ保持します。

`app/web/app.js` は 2,918 行の単一ファイルで、分割の分岐点に来ています。

### 音声パイプライン

`EDGE_AUDIO_PROCESSING_MODE=local`（既定）は園内で文字起こし・匿名化まで完了させ、
テキストだけを送ります。`cloud` は `CLOUD_AUDIO_ENABLED=true` も必要な明示的オプトインで、
音声は短命ジョブ保管に置かれ処理後に削除されます。
`SPEAKER_DIARIZATION_TOKEN` が設定されている場合は、両モードとも匿名話者分離を文字起こしへ統合します。
具体的な園児の出来事がない音声は記録を作らず、クラウドジョブだけを正常完了にします。
`LLM_ALLOW_EXTERNAL=false`（既定）のとき `LLM_BASE_URL` はループバックに限定され、
それ以外は `EdgeAudioError` で拒否されます。

## 変更するときに壊しやすいところ

- **資格情報は一度きりの表示。** 端末 APIキー・招待コード・アーカイブ URL はハッシュだけを保存し、
  再表示できません。紛失時は再発行して以前のものを失効させる、が既定の流れです。
- **`audit_events` に秘密情報を入れない。** 記録するのは操作の種類・日時・実行者の表示名だけ。
  園児名、通知文、LINE ユーザーID、対象の内部 ID は入れません。
- **`AUTH_MODE=development` は常に管理者扱い。** 認証を素通しし `isSchoolAdmin` も `true` 固定なので、
  一般の先生の画面はこのモードでは再現できません。外部公開も不可です。
- **`APP_ENV=production` は構成を検証して落とす。** `app/config.py` の
  `reject_unsafe_production_configuration()` が `AUTH_MODE=supabase`・非 SQLite・
  アーカイブの HTTPS を強制します。
- **`Settings` は `.env` を読む。** テストは `Settings(database_url=..., auth_mode="development")` を
  明示して各テストでアプリを作りますが、指定しなかった項目は実際の `.env` の値が入ります。
- **重複防止は一意制約で担保されています。** `records(school_id, source_event_id)`、
  `notifications.record_id`、`notion_syncs.record_id`、GPU ジョブの `claim_token` 排他取得。
- **Docker health と readiness を混同しない。** `/health` はAPIとDBの起動順だけに使い、
  `/readiness` は `worker_heartbeats` を含む運用開始判断に使います。ワーカーは音声や本文をheartbeatへ保存しません。

## 画面を作るとき・レビューするとき

**デジタル庁デザインシステム（DADS）に準拠する。** 原文は `docs/reference/dads/` に無改変で置いてあり、
トークンの値は `docs/design-system-digital-agency.md` にある。色や余白を決める前に、
該当する `docs/reference/dads/foundations/<領域>/index.md` を読むこと。要約で代用しない。

新しい画面・部品を作るときも、既存を review するときも、次は必ず確認する。

| 項目 | 基準 |
| --- | --- |
| コントラスト | テキストは背景に対して 4.5:1 以上（WCAG 1.4.3）。枠線・アイコンなど非テキストは 3:1 以上（1.4.11） |
| 色以外の手がかり | 色だけで情報を区別しない（1.4.1）。状態はアイコンや文言も併せて示す |
| フォーカス表示 | Yellow-300（`#ffd43d`）と Black の2重構造。DADS は「いかなる場合も変更してはいけない」と規定している |
| 余白 | 基準単位 8px の倍数。スケールは 3〜5 段階に収める |
| 書体 | Noto Sans JP / Noto Sans Mono。ウェイトは 400 と 700 のみ。和文の行送りは 1.75 まで使ってよい |
| セマンティック色 | 用途で選ぶ。アイコン・枠線には `-1`（3:1）、文字には `-2`（4.5:1） |
| 角丸 | 同じ半径でも図形が小さいほど丸く見える。部品の大きさごとに半径を決める |

レビューで指摘するときは、根拠になる DADS のページを併記する。

**現時点で分かっているズレ**（直すときはここから）:

- `--line`（`#d6dbe0`）は白背景に対して 1.39:1。31 箇所の枠線に使われており、識別に必要な境界では 3:1 に届かない
- グレーが青みを帯びている（`#f7f8f9`〜`#111820`）。DADS は純粋な無彩色
- 余白に 8px の倍数でない値が 8 種類・57 箇所ある（`0.125rem`〜`0.875rem`）。トークン 7 段と合わせて実効 15 段で、DADS の「3〜5 段階」から外れている

## ドキュメント

`docs/` に領域別の設計文書があります。実装前にこちらを読むと早いです。

| 領域 | ファイル |
| --- | --- |
| 索引・全体図 | `docs/architecture.md` |
| API サーバー | `docs/architecture/api.md` |
| データモデル・状態遷移 | `docs/architecture/data-model.md` |
| 音声パイプライン | `docs/architecture/audio-pipeline.md` |
| 認証・認可 | `docs/architecture/auth.md` |
| 外部連携（LINE / Notion / アーカイブ） | `docs/architecture/integrations.md` |
| フロントエンド | `docs/architecture/frontend.md` |
| デプロイ・運用 | `docs/architecture/deployment.md` |
| 画面遷移 | `docs/transition.md` |
| 参考デザインシステム | `docs/design-system-digital-agency.md` / `docs/reference/dads/` |

運用手順とセットアップの詳細は `README.md`、設定項目の一覧は `.env.example` にあります。
