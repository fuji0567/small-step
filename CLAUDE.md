# CLAUDE.md

This file provides guidance to coding agents (Claude Code, Codex) when working with code in this repository.
`AGENTS.md` points here, so add or change instructions in this file only.

Small Step（お便りAI）は、園で生まれた子どもの小さな成長を保護者へ届け、
家庭でもその成長を具体的に褒めてもらえる機会を増やすためのサービスです。
先生が装着する録音端末で普段の声かけを取得し、幼稚園の会話から「成長の記録」「けがの記録」の
候補を作り、**先生が内容と対象園児を確認・承認したものだけ** を保護者の LINE へ配信します。
UI・ドキュメント・ユーザー向け文言はすべて日本語です。

## プロダクトの目的

最終的な価値は、先生の入力作業を自動化することではなく、園でしか見えなかった子どもの頑張りを家庭へ届け、
保護者が「今日は五段も積めたんだね。頑張ったね」のように、具体的な出来事を基に褒められるようにすることです。
先生の記録負担の軽減、装着型録音端末、文字起こし、話者推定、LLM による記録候補生成は、その価値を実現するための手段です。

機能・画面・文章を設計するときは、次を優先してください。

- 子どもの小さな成長や挑戦が、保護者に具体的に伝わること
- 保護者が子どもへ前向きな声をかけるきっかけになること
- 先生が子どもと関わる時間を減らさず、安全に内容を確認・修正できること
- AI が人物や出来事を断定せず、最終判断を必ず先生に委ねること
- 記録件数を増やすことより、本人の尊厳とプライバシーを守ること

中心にある制約は **生音声と生の文字起こしを API のデータベースへ持ち込まない** こと。
匿名化は園内のエッジ端末で済ませ、`POST /api/v1/edge/records` には加工済みテキストだけが届きます。
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
python scripts/send_pending_line_notifications.py --dry-run   # LINE 送信なし（未連携の期限到来通知は failed に更新）
python scripts/send_pending_line_notifications.py --watch      # LINE 送信ワーカー（常駐）
python scripts/process_cloud_audio_jobs.py                     # GPU ワーカー（常駐・VRT 用）
python -m app.mcp_server --streamable-http --port 8002          # MCP（ローカル専用）
```

```bash
docker compose up -d --build                                        # api のみ
docker compose -f compose.yaml -f compose.vrt.yaml up -d --build    # migrate + gpu-worker + line-worker
```

フロントエンドは Node.js 24.19.0 を使います。FastAPI を起動したうえで、別ターミナルから実行します。

```bash
cd frontend
npm ci
npm run dev                 # /api/v1 を FastAPI へ proxy
npm run format
npm run format:check
npm run lint
npm run check
npm run test:unit
npm run test:e2e:install    # 初回だけ
npm run test:e2e
npm run build               # ../app/frontend_dist を生成
```

日常の開発手順は [README](README.md#フロントエンド開発)、配信条件は
[デプロイ設計](docs/architecture/deployment.md) を正とします。

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

全 57 エンドポイントが `app/api/routes.py`（2,300 行超）に入っています。
園スコープと管理者判定は、ミドルウェアに隠さず **各ハンドラの冒頭で明示的に呼ぶ** のがこのリポジトリの慣習です
（`assert_school_access` / `assert_school_admin`）。新しいハンドラでも同じ形を踏襲してください。

### データベースは二重運用

ローカルは SQLite（`./data/otayori.db`、起動時に自動移行）、本番・VRT は PostgreSQL で
`scripts/prepare_database.py` を明示実行（Compose の `migrate` サービス）。
移行ファイルは `migrations/`、Alembic 管理です。SQLite の自動適用は本番では使いません。

### フロントエンドは SvelteKit の静的ビルド

`frontend/` は Svelte 5 runes、TypeScript、SvelteKit で構成し、Node.js 24.19.0 でビルドします。
`@sveltejs/adapter-static` の生成先は `app/frontend_dist/` です。FastAPI は `/guardian/` の
prerender 済みページと `/_app/*` を静的配信し、`/teacher/*` だけを `200.html` へ SPA fallback します。

- 先生用は `/teacher/` 以下のファイルベースルーティングを使います。日誌 1 件にも
  `/teacher/review/{recordId}/` があり、直接表示・再読み込み・Back / Forward を復元します。
- 保護者用は `/guardian/` の静的ページです。`#ssa_...` はルートではなく資格情報であり、
  `sessionStorage` へ保存して URL から消してから API を呼びます。
- API は同一オリジンの `/api/v1` を呼び、認可の本体は引き続き FastAPI です。
- 先生用のアクセストークンは `sessionStorage`（`small-step.access-token`）にのみ保持します。
- 外部フォントや CDN は使わず、アイコンはローカル SVG です。先生用画面は外部オリジンへ通信しません。

`app/web/` と `app/guardian/` はロールバック用にファイルを保持していますが、現在の URL にはマウントされません。
構成とテスト責務の詳細は `docs/architecture/frontend.md` を参照してください。

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

機能を実装するときは、実装箇所を推測してコードから直接探索し始めないでください。
まず `docs/architecture.md` と該当領域の設計文書を読み、機能の責務、処理の流れ、関連モジュール、
既存の判断を把握して、変更候補を大まかに絞ります。その見当を付けてから実コードを確認し、実装に入ります。

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

### コミット時のドキュメント整合

コミットする前に、変更した実装・設定・運用手順と `README.md`、`.env.example`、`docs/` の記述に
矛盾がないことを必ず確認してください。差異がある場合は、先に関連ドキュメントを更新してからコミットし、
実装とドキュメントの変更を同じコミットに含めます。
