# Small Step（お便りAI）

幼稚園での会話から「成長の記録」「けがの記録」の候補を作り、先生が確認・承認した文面を
保護者のLINEへ届けるアプリです。先生用画面、保護者向け配信アーカイブ、スマートフォン録音PWA、
FastAPIバックエンドをこのリポジトリで管理しています。

新しく登録した園は**試用モード**で開始します。録音・候補作成・承認は試せますが、保護者へは配信しません。
本番に切り替えても、以前の試用記録は配信されません。

## 使い方

1. 先生管理者が園、先生、園児を登録します。保護者のLINE連携は「園児・保護者」で発行する招待コードを使います。
2. 先生が手入力するか、有効化済みの録音PWA・録音端末から記録候補を作ります。
3. 「レビュー待ち」で対象園児と本文を確認し、必要なら補正して承認または却下します。
   録音由来の記録では園児確認チェックも必要です。
4. 本番の承認済み記録はLINE送信ワーカーが配信します。成長記録は園の配信時刻（既定17:00）、
   けがの記録は即時が既定です。日時を指定した場合はその予約を使います。
5. 「通知状況」で結果を確認します。LINE未連携なら連携待ち、試用なら配信なしです。
   先生管理者は失敗した通知の再送を予約できます。

| 入口 | 対象 | 用途 |
| --- | --- | --- |
| `/teacher/` | 先生・先生管理者 | 記録のレビュー、履歴、通知、園の管理 |
| `/rec/` | ログインした先生 | スマートフォンでの録音。機能有効時だけ配信 |
| `/guardian/#ssa_...` | URLを受け取った保護者 | その園児への送信済み通知を閲覧。機能有効時だけ利用 |
| `/docs` | 開発者・管理者 | 起動中APIのOpenAPI仕様 |

一般の先生は自分が担当する記録と通知を扱います。園児・先生・端末の管理、通知の再送・取消、
CSV書き出し、操作履歴、Notion同期は先生管理者の操作です。
詳細は[先生・保護者の使い方](docs/usage.md)、[スマートフォン録音](docs/recorder-usage.md)を参照してください。

## ローカルで起動

Python 3.11以上（DockerのAPIは3.12）と、両フロントエンドの指定に合わせたNode.js 24.19.0を用意します。
以下はリポジトリのルートで実行するWindows PowerShellの例です。

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev]"

cd frontend
npm ci
npm run build
cd ..

.venv/Scripts/python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

macOS/Linuxでは仮想環境のPythonを `.venv/bin/python` と読み替えます。
新規の `.env.example` はSQLite・認証なしの開発設定です。既存の `.env` がある場合は設定を確認してください。
`AUTH_MODE=development` は管理者相当で動作するローカル専用モードです。

起動後に[先生用画面](http://127.0.0.1:8000/teacher/)と[API仕様](http://127.0.0.1:8000/docs)を開きます。
空のDBでは、API仕様画面の `POST /api/v1/schools` から `{"name":"テスト園"}` を送って園を作成し、
先生用画面で選択します。「園児・保護者」でテスト園児を登録し、「レビュー待ち」の「手入力で追加」から
候補を作ると、音声やLINEの設定なしで試用承認まで確認できます。
SQLiteの移行は起動時に自動適用されます。画面が404ならフロントエンドのビルドを確認してください。

DockerでAPIと先生・保護者画面を試す場合は、`.env` を用意して次を実行します。ビルド中にUIの検証も行います。

```bash
docker compose up -d --build
```

最小ComposeはAPIだけを起動します。LINEやGPUワーカーは別途起動が必要です。

## 録音とデータの扱い

既定のローカル処理では、園内の端末で文字起こし・匿名化し、APIへ加工済みテキストだけを送ります。
クラウド音声処理と録音PWAを明示的に有効にした場合は、生音声をAPI経由で短命ファイルへ一時保管し、
GPUワーカーが処理します。音声と生の文字起こしは業務DBへ保存しません。

録音PWAは前面表示中に使います。既定の連続モードは開始操作後、60秒ごとに別セッションとして自動送信し、
停止時の端数も送ります。最長12時間、端末に未送信が3件残ると一時停止します。手動モードは最長60分で、
停止後に送信または破棄を選びます。画面ロックやスリープ中の常時録音は保証しません。

匿名化の完全性や園児・先生候補の正しさは保証しません。候補だけで対象を確定せず、先生が本文と園児を確認します。
声紋とプロコン用処理表示は別の任意機能で、同意・機能設定・短命保管などの条件があります。
詳細は[共通仕様](docs/specification.md)と[音声処理仕様](docs/architecture/audio-pipeline.md)にまとめています。

## 技術構成

| 領域 | 技術・役割 |
| --- | --- |
| API | Python、FastAPI、Uvicorn、Pydantic v2 |
| DB | SQLAlchemy 2、Alembic。開発はSQLite、本番はPostgreSQL |
| 先生・保護者画面 | Svelte 5、TypeScript、SvelteKit、adapter-static |
| 録音PWA | 独立したSvelte 5＋Vite、MediaRecorder、IndexedDB、Service Worker |
| 認証 | 先生はSupabase Auth、録音端末は専用APIキー、保護者は期限付き不透明トークン |
| 音声処理 | faster-whisper、任意のpyannote.audio、OpenAI互換LLM（Ollama / vLLM） |
| 外部連携 | LINE Messaging API、任意のNotion同期、ローカルMCP |
| 配備・運用 | Docker Compose、任意のVRT GPU、バックアップ・内部／外部監視 |

先生・保護者画面の生成先は `app/frontend_dist/`、録音PWAは `app/recorder_dist/` です。
FastAPIが静的ファイルを配信し、業務APIは同じオリジンの `/api/v1` を使います。
認証時はブラウザからSupabaseへ直接通信します。LINE送信・GPU処理ワーカーは共通のDBを直接使います。
構成図と領域別仕様は[技術構成の索引](docs/architecture.md)を参照してください。

## フロントエンド開発

FastAPIをポート8000で起動したうえで、別ターミナルで実行します。Viteは `/api/v1` をFastAPIへ転送します。

```bash
cd frontend
npm ci
npm run dev
```

録音PWAを開発するときは、別ターミナルで `recorder_frontend/` に移動して `npm ci`、`npm run dev` を実行します。
APIと静的配信の有効化条件は[録音導入手順](docs/recorder-vrt-runbook.md)を参照してください。

変更に応じた検証を行います。以下の共通コマンドは両packageにあります。

```bash
npm run format:check
npm run lint
npm run check
npm run test:unit
npm run build
```

先生・保護者画面のE2Eは `frontend/` だけで実行します。

```bash
npm run test:e2e:install  # 初回だけ
npm run test:e2e
```

バックエンドのテストはルートで `.venv/Scripts/python.exe -m pytest` を実行します。
テスト用設定にも、指定していない項目は `.env` から入ります。使用環境を確認してから実行してください。

## 導入・運用の手順

| 目的 | 手順書 |
| --- | --- |
| 先生認証・DB・LINE・録音端末の初期設定 | [初期設定](docs/operations/setup.md) |
| エッジ音声、VRT、MCP、音声評価 | [音声導入と検証](docs/operations/audio.md) |
| バックアップ・復元確認・内部／外部監視 | [バックアップと監視](docs/operations/backup-monitoring.md) |
| 新しい園での試用と本番への切り替え | [園別試用モード](docs/school-trial-runbook.md) |
| スマートフォン録音、園児・先生候補の有効化 | [録音導入](docs/recorder-vrt-runbook.md) |
| 管理画面からの先生招待 | [先生招待](docs/teacher-invitations.md) |
| 架空の会話によるプロコン実演 | [処理表示デモ](docs/recorder-processing-demo.md) |
| 配備先での合否確認 | [実機・外部サービス確認](docs/operations/acceptance.md) |

設定例は [.env.example](.env.example)、設定の制約は[API設計](docs/architecture/api.md#設定)を参照してください。
本番はSupabase認証・非SQLiteのDB・HTTPSの入口を用意します。設定例の値だけで運用開始とはしません。

文書の役割と矛盾点の整理結果は[文書一覧](docs/README.md)にあります。
エージェント向け作業指示は [CLAUDE.md](CLAUDE.md) に集約し、[AGENTS.md](AGENTS.md)から参照します。
