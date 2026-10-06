# Small Step（お便りAI）

園で見つかった子どもの小さな成長を家庭へ届け、保護者が具体的な出来事をもとに子どもを褒めるきっかけをつくるサービスです。先生が装着する録音端末やブラウザ録音の音声からAIが記録候補を作り、本番運用では先生が内容と対象園児を確認・承認した記録だけを保護者へ届けます。試用モードでは保護者へ配信しません。記録作業の負担軽減と音声AIは、この体験を支える手段です。

## 公開アプリ

- [先生用画面](https://app.otayori-ai.com/teacher/):
  先生がログインして記録候補を確認・承認します。
- [録音画面](https://app.otayori-ai.com/rec/):
  先生がログインして録音デモを利用します。利用可否はサーバー側の録音設定に従います。

このリポジトリにはFastAPIバックエンド、先生用Webアプリ、録音PWA、GPU音声処理ワーカーが含まれます。

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

| 入口                 | 対象                  | 用途                                               |
| -------------------- | --------------------- | -------------------------------------------------- |
| `/teacher/`          | 先生・先生管理者      | 記録のレビュー、履歴、通知、園の管理               |
| `/rec/`              | ログインした先生      | スマートフォンでの録音。機能有効時だけ配信         |
| `/guardian/#ssa_...` | URLを受け取った保護者 | その園児への送信済み通知を閲覧。機能有効時だけ利用 |
| `/docs`              | 開発者・管理者        | 起動中APIのOpenAPI仕様                             |

一般の先生は自分が担当する記録と通知を扱います。園児・先生・端末の管理、通知の再送・取消、
CSV書き出し、操作履歴、Notion同期は先生管理者の操作です。
詳細は[先生・保護者の使い方](docs/usage.md)、[スマートフォン録音](docs/recorder-usage.md)を参照してください。

## ローカルで起動

Python 3.11以上（DockerのAPIは3.12）と、両フロントエンドの指定に合わせたNode.js
24.19.0を用意します。 以下はリポジトリのルートで実行するWindows
PowerShellの例です。

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

macOS/Linuxでは仮想環境のPythonを `.venv/bin/python` と読み替えます。 新規の
`.env.example` はSQLite・認証なしの開発設定です。既存の `.env`
がある場合は設定を確認してください。 `AUTH_MODE=development`
は管理者相当で動作するローカル専用モードです。

起動後に[先生用画面](http://127.0.0.1:8000/teacher/)と[API仕様](http://127.0.0.1:8000/docs)を開きます。
空のDBでは、API仕様画面の `POST /api/v1/schools` から `{"name":"テスト園"}`
を送って園を作成し、
先生用画面で選択します。「園児・保護者」でテスト園児を登録し、「レビュー待ち」の「手入力で追加」から
候補を作ると、音声やLINEの設定なしで試用承認まで確認できます。
SQLiteの移行は起動時に自動適用されます。画面が404ならフロントエンドのビルドを確認してください。

DockerでAPIと先生・保護者画面を試す場合は、`.env`
を用意して次を実行します。ビルド中にUIの検証も行います。

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

| 領域             | 技術・役割                                                                 |
| ---------------- | -------------------------------------------------------------------------- |
| API              | Python、FastAPI、Uvicorn、Pydantic v2                                      |
| DB               | SQLAlchemy 2、Alembic。開発はSQLite、本番はPostgreSQL                      |
| 先生・保護者画面 | Svelte 5、TypeScript、SvelteKit、adapter-static                            |
| 録音PWA          | 独立したSvelte 5＋Vite、MediaRecorder、IndexedDB、Service Worker           |
| 認証             | 先生はSupabase Auth、録音端末は専用APIキー、保護者は期限付き不透明トークン |
| 音声処理         | faster-whisper、任意のpyannote.audio、OpenAI互換LLM（Ollama / vLLM）       |
| 外部連携         | LINE Messaging API、任意のNotion同期、ローカルMCP                          |
| 配備・運用       | Docker Compose、任意のVRT GPU、バックアップ・内部／外部監視                |

先生・保護者画面の生成先は `app/frontend_dist/`、録音PWAは `app/recorder_dist/`
です。 FastAPIが静的ファイルを配信し、業務APIは同じオリジンの `/api/v1`
を使います。
認証時はブラウザからSupabaseへ直接通信します。LINE送信・GPU処理ワーカーは共通のDBを直接使います。
構成図と領域別仕様は[技術構成の索引](docs/architecture.md)を参照してください。

## フロントエンド開発

FastAPIをポート8000で起動したうえで、別ターミナルで実行します。Viteは `/api/v1`
をFastAPIへ転送します。

```bash
cd frontend
npm ci
npm run dev
```

録音PWAを開発するときは、別ターミナルで `recorder_frontend/` に移動して
`npm ci`、`npm run dev` を実行します。
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

<<<<<<< HEAD バックエンドのテストはルートで `.venv/Scripts/python.exe -m pytest`
を実行します。 テスト用設定にも、指定していない項目は `.env`
から入ります。使用環境を確認してから実行してください。

## 導入・運用の手順

| 目的                                       | 手順書                                                     |
| ------------------------------------------ | ---------------------------------------------------------- |
| 先生認証・DB・LINE・録音端末の初期設定     | [初期設定](docs/operations/setup.md)                       |
| エッジ音声、VRT、MCP、音声評価             | [音声導入と検証](docs/operations/audio.md)                 |
| バックアップ・復元確認・内部／外部監視     | [バックアップと監視](docs/operations/backup-monitoring.md) |
| 新しい園での試用と本番への切り替え         | [園別試用モード](docs/school-trial-runbook.md)             |
| スマートフォン録音、園児・先生候補の有効化 | [録音導入](docs/recorder-vrt-runbook.md)                   |
| 管理画面からの先生招待                     | [先生招待](docs/teacher-invitations.md)                    |
| 架空の会話によるプロコン実演               | [処理表示デモ](docs/recorder-processing-demo.md)           |
| 配備先での合否確認                         | [実機・外部サービス確認](docs/operations/acceptance.md)    |

設定例は
[.env.example](.env.example)、設定の制約は[API設計](docs/architecture/api.md#設定)を参照してください。
本番はSupabase認証・非SQLiteのDB・HTTPSの入口を用意します。設定例の値だけで運用開始とはしません。

# 文書の役割と矛盾点の整理結果は[文書一覧](docs/README.md)にあります。 エージェント向け作業指示は [CLAUDE.md](CLAUDE.md) に集約し、[AGENTS.md](AGENTS.md)から参照します。

検証は
`npm run format:check`、`npm run lint`、`npm run check`、`npm run test:unit`、`npm run build`
の順です。 ビルド成果物は `app/recorder_dist/`
に生成され、`RECORDER_ENABLED=true` のときだけ `/rec/` で配信されます。
録音APIも初期状態では無効です。現段階で実装済みなのは、先生認証、約1分ごとの独立ファイル化、IndexedDBへの
24時間・最大3件の一時保存、冪等な分割送信、既存GPUワーカーでの連番処理と匿名化済み候補の段階統合です。
既定の「連続録音」は、明示的な開始後に60秒ごとに別セッションとして自動送信し、録音を続けます。
停止時の端数も送信します。1回の開始で最長12時間、未送信が3区間に達すると一時停止し、利用者が明示的に再開します。
画面の背面への切り替えだけでは一時停止せず、ブラウザが動作している間は録音と連続モードの自動送信を継続します。
マイク中断・ブラウザによる録音停止では端数を確定して一時停止し、利用者が明示的に再開します。
iPhone・iPadの画面ロック・スリープ・ページ終了中の常時録音は保証しません。OSがマイク・タイマー・通信を
止める場合があり、ホーム画面への追加でも制約は解消しません。確実に録音するには画面を開いたままにします。
ESPの無人常時録音と同等ではありません。
チェックを外した手動モードは従来どおり最長60分、停止後に送信または破棄を選びます。
1セッションから園児未選択の承認待ち記録を最大1件作成し、処理進捗と部分失敗の警告を先生用画面に表示します。
`RECORDER_CHILD_MATCHING_ENABLED=true`
では、同じ園の登録表示名と管理者が登録した「録音で呼ぶ名前」から
園児候補を提案します。呼び名・読み方は園児の「表示名を編集」で敬称なし・2〜40文字・最大5件を登録します。
カタカナとひらがな、全角半角を正規化しますが、姓や読み方の推測・曖昧検索はしません。
名前だけで紐付けず、LLMが具体的な出来事の対象だと判定した一人だけを提案し、同名（退園者を含む）、
複数人、曖昧な対象、部分処理失敗では未選択です。候補の精度は実機での確認が必要です。
先生用の詳細画面では有効な候補を仮選択しますが、実際の `child_id`
は承認時まで未選択です。
録音由来の記録は手動選択の場合も含め、先生が園児確認チェックを入れて承認するまで配信先に使いません。
既知の園児名はLLM入力で一時参照へ置換し、生成本文から既知の名前・参照を除きます。
未登録名や誤変換名の完全な匿名化は保証できないため、承認前に本文も必ず確認してください。
録音PWAの受付画面でも状態を約5秒ごとに確認し、区間ごとの進捗と作成された記録へのリンクを表示します。
非表示・オフライン中は確認を停止して復帰時に再開します。状態確認はGETだけで、受付済み音声の再送や自動承認は行いません。
待機画面へ戻った後や再読み込み後の結果は、先生用「音声処理状況」で確認します。
成功・失敗・破棄・期限切れ後の音声は削除し、ワーカー起動時と定期処理で後片付けを再試行します。
モデルを二重起動する専用ワーカーは追加しません。実機での試験導入までは
`RECORDER_ENABLED=false` を維持し、
[VRT録音デモ導入手順](docs/recorder-vrt-runbook.md)に従って有効化してください。

プロコンで処理の流れを説明する場合は、[処理表示デモ手順](docs/recorder-processing-demo.md)を使います。
試用モード・本人ログイン・録音前の同意がそろった録音だけ、文字起こし、実際のLLMへの指示／入力／JSON応答、
形式検証、園児・先生候補の照合結果を録音画面に表示します。内部思考や推測した判定理由は表示しません。
`RECORDER_DEMO_TRACE_ENABLED=false`
が既定です。内容は専用キーで暗号化した短命ファイルにのみ置き、
処理終了から5分後には取得できなくなり、定期処理で削除します。通常のDB・ログには保存しません。
この例外的な表示には架空の人物だけを使い、実際の園の会話を使用しないでください。

録音PWAは `small-step.access-token`
を同じブラウザセッション内で再利用し、独自ログイン時の更新トークンも 録音専用の
`sessionStorage`
にだけ保存します。通信復旧時の自動再送は、利用者が「送信する」を選んだ後に中断した
セッションと、連続録音の開始時に自動送信へ同意した確定済み区間だけを対象とします。
手動モードの録音中や停止後の確認中に別タブから確定しません。Service
WorkerはAPI応答、認証情報、音声をキャッシュしません。
入口は信頼できる証明書のHTTPS（公開ドメインまたは園内CA）だけにし、FastAPIの8000番ポートをLANへ直接公開しないでください。

レビュー時は、在籍中の園児を必ず選択してから承認します。園児未選択の候補は承認できず、通知も作成されません。配信日時を空欄のまま承認すると既定ルールが使われます。成長記録は園ごとの配信時刻、怪我記録は即時の送信待ちです。必要な場合だけ「配信日時を指定する」を選び、保護者へ送る日時を予約できます。

先生管理者は、レビュー待ち日誌の詳細から同じ園の有効な先生へ担当を変更できます。引き継いだ日誌は新しい担当先生のレビュー待ち一覧へ移り、元の担当先生からは見えなくなります。承認・却下・配信済みの記録は履歴を保つため変更できず、担当変更は操作履歴に記録されます。

音声がない場面では、「レビュー待ち」の「手入力で追加」から成長記録または怪我記録を作成できます。手入力した記録も必ずレビュー待ちになり、承認するまで保護者へ配信されません。本番ではログイン中の先生へ自動で紐付きます。

### 園の設定

先生管理者は「園の設定」で、成長記録の既定配信時刻を園ごとに変更できます。変更後に承認する成長記録だけへ適用され、すでに送信待ちの通知時刻は変わりません。怪我記録はこの設定に関係なく即時に送信待ちになります。新しい園を作るときは
`.env` の `DIGEST_TIME` が初期値になります。

### 園児・保護者管理

先生用画面の「園児・保護者」では、園児一覧と保護者LINEの連携状態を確認できます。`school_admin`
の先生だけが園児を追加・表示名を修正し、未連携の園児向けに60分有効の招待コードを発行できます。保護者はLINE公式アカウントのトークにそのコードだけを送信して連携します。LINEのユーザーIDや保護者のメッセージ本文はこの画面に表示しません。

誤連携や保護者の変更時は、連携済み園児の「LINE連携を解除」を使えます。未送信通知、未使用の招待コード、保護者用配信アーカイブURLは即時に無効化されます。すでにLINE
APIへ送信を開始した通知は取り消せません。

保護者LINEが未連携の園児で記録を承認した場合、通知は失敗にせず「保護者LINEの連携待ち」として保留されます。先生管理者は通知状況から「園児・保護者を開く」を選び、招待コードを発行できます。保護者がコードで連携すると、その園児の連携待ち通知は送信待ちになり、設定済みの配信時刻以後に送信ワーカーが配信します。

退園時は「退園にする」を使います。過去の記録は履歴として残りますが、園児はレビュー時の選択肢から外れ、未レビュー記録は却下、送信待ち通知は取消、保護者LINE・招待コード・配信アーカイブURLは無効になります。処理中または待機中のクラウド音声ジョブも停止して、生音声を削除します。誤って退園処理した場合は、先生管理者だけが「復園に戻す」を使えます。復園では園児だけを在籍へ戻し、以前の保護者LINE連携・通知・音声・招待コード・アーカイブURLは復活しないため、必要なら新しい招待コードから連携し直します。

### 保護者Webの配信アーカイブ

LINE連携済みの園児について、先生管理者は「園児・保護者」から保護者専用の配信アーカイブURLを発行できます。アーカイブには、その園児へ**送信済み**になった通知だけを表示します。LINEユーザーID、先生情報、内部ID、音声、文字起こしは表示しません。

この機能は初期状態で無効です。テストまたは運用を始める前に、HTTPSで公開するURLと、保護者本人のLINEトークへ個別送信する運用を決めてから有効にしてください。

```dotenv
GUARDIAN_ARCHIVE_ENABLED=true
GUARDIAN_ARCHIVE_BASE_URL=https://<公開するSmall StepのURL>
GUARDIAN_ARCHIVE_LINK_TTL_HOURS=168
```

URLの秘密部分は `#`
より後ろに置くため、保護者が最初にページを開くHTTPリクエストやリファラーには含まれません。発行時にだけ先生画面へ表示され、同じ園児で新しいURLを発行すると、古いURLは即時に無効になります。URLはパスワードと同じ扱いです。保護者本人以外に転送せず、紛失・誤送信時は新しいURLを発行して以前のURLを失効してください。

### 先生管理

`school_admin`
の先生は、先生用画面の「先生管理」で名前とメールアドレスを登録できます。
招待送信を設定済みなら「登録して招待を送る」で登録・メール送信を続けて行います。
既存の未連携の先生も一覧から招待・再送できます（同じ先生への送信は1分以上空けます）。
送信失敗やタイムアウトでも先生登録は残り、メールが届いていなければ一覧から再試行できます。
メールから開いた先生用画面で本人がパスワードを設定し、初回ログイン時に先生情報を紐付けます。
「招待送信済み」はSupabaseが送信を受け付けた状態で、メール到着や本人ログインの完了ではありません。
設定方法とメール送信制限は [先生招待の導入手順](docs/teacher-invitations.md)
を参照してください。 招待送信が未設定の場合は従来どおりSupabase
Dashboardから同じメールへ招待できます。
パスワードはブラウザからSupabaseへ直接渡し、FastAPIのDB・ログには保存しません。

退職・異動時は、先生管理者が「利用停止」を実行できます。停止後はSmall
Stepへのログイン、担当録音端末、待機中の音声処理を止めます。既に作られた記録と通知は園の履歴として残ります。誤操作時は「利用を再開」で先生アカウントだけを戻せますが、以前の端末キー・待機音声・声紋設定は復活しません。最後の有効な先生管理者と、自分自身のアカウントは利用停止にできません。

管理者の引き継ぎでは、既存の先生管理者が引き継ぎ先の先生を「管理者にする」操作を行います。新しい管理者がログインできることを確認してから、その新しい管理者が元の管理者を「先生に戻す」か「利用停止」にします。最後の有効な先生管理者は通常の先生へ戻せません。また、自分自身の権限は変更できません。これらの操作は「操作履歴」に種類・日時・実行者だけを記録します。

### 録音端末管理

`school_admin`
の先生は、先生用画面の「録音端末」で端末名と担当の先生を選んで録音端末を登録できます。登録時または鍵の再発行時だけ、端末を接続するための専用キーが表示されます。表示中にコピーして端末側の
`.env` の `EDGE_API_KEY`
に設定してください。安全のため、発行済みのキーは一覧や再表示画面には残りません。

端末の最終接続日時と有効・無効の状態は一覧で確認できます。使わなくなった端末は「無効化」で直ちに通信を止められます。再び使う場合は鍵を再発行すると、古い鍵を使えなくしたうえで端末を有効化できます。

録音監視プログラムは既定で60秒ごとに、音声・ファイル名・文字起こしを含まない稼働通知を送ります。先生画面の「録音端末」には、稼働通知や記録・音声の受信で更新される最終接続日時を表示します。端末のネットワーク不調や電源断に早く気づくための目安であり、録音・アップロードの成功を保証する表示ではありません。

### 操作履歴

`school_admin`
の先生は、先生画面の「操作履歴」で最新100件の運用操作を確認できます。記録の担当変更・承認・却下・手入力、記録履歴と操作履歴のCSV出力、通知の再送予約・日時変更・取消、招待コードの発行、保護者LINEの連携と解除、配信アーカイブURLの発行と無効化、園児の修正・退園・復園、先生の利用停止・再開・権限変更、園の配信時刻変更、録音端末の登録・キー再発行・無効化、Notionへの記録が対象です。一般の先生は閲覧できません。

履歴に保存・表示するのは操作の種類、実行日時、実行した先生の表示名だけです。園児名、通知文、音声、文字起こし、LINEユーザーID、招待コード、アーカイブURL、端末キー、操作対象の内部IDは保存・表示しません。LINEから保護者が連携した操作は、実行者を`システム`として表示します。先生管理者は操作の種類・実行期間で絞り込み、最大1,000件をCSVで出力できます。CSVには実行者の表示名だけが含まれるため、園の運用管理以外には共有しないでください。

MCP（Model Context
Protocol）サーバーは、マイクに近い園内PCまたは高火力VRTのGPUワーカーで動かします。公開するFastAPIやLINE
Webhookで動かすものではありません。

```text
ローカル音声ファイル
  -> faster-whisper（ローカル文字起こし）
  -> ローカルLLM（匿名化した記録候補の作成）
  -> MCPツール
  -> エッジAPIキー付きのFastAPI
  -> 先生の承認
  -> LINE通知
```

MCPサーバーは次の3つだけを公開します。

- `edge_audio_status`: 秘密情報を返さず、設定の準備状況だけを確認する。
- `analyze_audio_file`:
  許可したローカルフォルダ内の音声を、匿名化済み候補へ変換する。APIへは保存しない。
- `submit_analyzed_audio_file`:
  匿名化済み候補を先生の承認待ち記録として登録する。LINE送信はできない。

### 安全な前提

- 音声ファイルは `EDGE_AUDIO_INBOX_DIR` 配下の
  `.wav`、`.mp3`、`.m4a`、`.ogg`、`.flac` だけを受け付けます。
- 既定では処理の成否にかかわらず音声ファイルを削除します。生の文字起こしもDB・API応答・MCP応答へ保存しません。
- LLMの接続先は既定で `localhost`
  だけです。外部ホストを使うには、リスクを確認して `LLM_ALLOW_EXTERNAL=true`
  を明示する必要があります。
- `injury`
  と判定されても、必ず先生の承認を通ります。MCPやLLMだけでLINE通知されることはありません。

### 高火力 VRTでクラウド音声処理する準備

園内の高性能PCを置かず、さくらの高火力
VRTへ音声を送ってGPU処理するためのジョブ基盤を用意しています。最初の実証では、FastAPIとGPUワーカーを**同じVRT**で動かし、同じ非公開ディレクトリを共有します。録音端末は登録済みの端末キーで、`multipart/form-data`
の `audio` ファイルを `POST /api/v1/edge/audio-jobs` へ送信します。

クラウド音声モードは初期状態で無効です。園・先生・保護者への説明と同意、通信経路、運用責任者を決めるまで
`false` のままにしてください。

```dotenv
CLOUD_AUDIO_ENABLED=true
CLOUD_AUDIO_JOB_DIR=/var/lib/small-step/cloud-audio-jobs
CLOUD_AUDIO_JOB_RETENTION_MINUTES=15
CLOUD_AUDIO_PROCESSING_TIMEOUT_MINUTES=10
EDGE_AUDIO_DEVICE=cuda
EDGE_AUDIO_COMPUTE_TYPE=float16
LLM_BACKEND=vllm
LLM_BASE_URL=http://127.0.0.1:8001/v1
LLM_MODEL=Qwen/Qwen3-32B
```

アップロードされた生音声には元のファイル名を付けず、ランダムIDで保存します。未処理ジョブは最大15分で期限切れになり、GPUワーカーは成功・失敗・記録対象外を問わず音声を削除します。処理中にVRTやワーカーが停止した場合は、既定10分後に次のワーカーが安全に引き継げます。具体的な園児の出来事が確認できた場合だけ匿名化済みの承認待ち記録を作り、無音、技術テスト、雑談、設定確認、先生だけの事務的な会話などは正常完了の「記録対象外」としてジョブ履歴だけを残します。Whisperが発話を検出しなかった場合はQwenを呼び出しません。

常駐するGPUワーカーとLINE送信ワーカーは、既定30秒ごとにワーカー名と最終確認時刻だけをデータベースへ記録します。90秒以上更新されない場合、先生画面の「稼働準備」は停止として表示します。長い音声処理中も別スレッドで更新するため、処理時間の長さを停止と誤判定しません。

録音端末は、VRTのAPIが準備できた後に端末側の `.env`
で次のように切り替えます。`cloud`
モードでは端末内の文字起こし・LLMは起動せず、VRTが受信に成功したときだけ端末の音声ファイルを削除します。通信失敗時は端末に残るため、次回の監視で再送できます。

```dotenv
EDGE_AUDIO_PROCESSING_MODE=cloud
EDGE_API_URL=https://<VRTの非公開URLまたはHTTPS公開URL>
EDGE_API_KEY=<その録音端末専用のキー>
EDGE_DEVICE_HEARTBEAT_INTERVAL_SECONDS=60
```

VRT側では `CLOUD_AUDIO_ENABLED=true` を設定します。端末・VRTともに `.env`
はGitへ追加しません。

VRTとの通信が一時的に切れた場合、端末は音声を削除せずに残します。再接続後は10秒、20秒、40秒のように待機時間を延ばしながら再送します（最大5分）。同じ音声には端末内だけで管理するランダムな送信IDを付けるため、サーバーの受信結果が通信途中で分からなくなった場合も、VRT上に同じ音声ジョブを二重に作りません。送信を受け付けた応答を確認できたときだけ端末側の音声を削除します。

30秒区切りの前後で同じ出来事が重複して候補化された場合は、同じ園児・同じ録音端末・同じ種別・2分以内・未承認で、要約がほぼ同じものだけを既存の記録へまとめます。園児未選択、承認済み、文章が異なる候補は自動統合しません。

VRT上では、FastAPIを起動した後に別プロセスでGPUワーカーを起動します。`--once`
は1回だけの安全な検証用です。

```bash
.venv313/bin/python -m pip install -e '.[edge-audio,speaker-diarization]'
.venv313/bin/python scripts/process_cloud_audio_jobs.py --once
```

通常運用では `--once`
を外します。待機中ジョブの取得はDBで原子的に行うため、複数のGPUワーカーを誤って起動しても同じジョブを同時に処理しません。最初のVRTではGPUメモリ管理を単純にするため、まずは1プロセスで運用してください。APIとGPUワーカーを別VMへ分ける段階では、次に暗号化したオブジェクトストレージとキューへ置き換えます。

### VRT音声処理の一括確認

録音端末を実機運用へ切り替える前に、音声1件のアップロード、端末キー、GPUワーカー、
記録候補作成を一度に確認できます。元の音声は削除せず、処理結果は先生の承認待ちまでで止まるため、
このコマンドだけでLINEへ送信されることはありません。

```bash
.venv313/bin/python scripts/verify_vrt_audio_pipeline.py \
  data/edge-audio-inbox/test.wav \
  --api-url http://127.0.0.1:18000
```

外部URLを直接指定する場合はHTTPSだけを受け付けます。`http://127.0.0.1`はSSH転送中の
ローカル接続に限って利用できます。端末キーは`.env`の`EDGE_API_KEY`または非表示入力から読み、
画面や結果へ表示しません。園児を決めずに確認した場合は、作成された候補を先生画面で選択します。

### 実音声テストセットの精度確認

複数話者、声量差、雑音、記録対象外を含む複数の音声は、匿名のケースIDと期待値を
マニフェストへ記載して順番に評価できます。ひな形は
[`docs/vrt-audio-evaluation-manifest.example.json`](docs/vrt-audio-evaluation-manifest.example.json)です。
音声はGit対象外の`data/vrt-evaluation/`へ置き、人物名をケースIDやファイル名に使わないでください。

```bash
.venv313/bin/python scripts/evaluate_vrt_audio_samples.py \
  docs/vrt-audio-evaluation-manifest.example.json \
  --api-url http://127.0.0.1:18000 \
  --interactive-review
```

VRTの受付状態を一度確認してから、ケースを1件ずつ処理します。評価項目は検出話者数、
記録候補の作成有無、成長／怪我の分類、誤検出・見逃し、音量差補正の使用有無、処理時間の
中央値・95パーセンタイルです。`--interactive-review`を付けると候補作成後に処理を一時停止し、
先生画面で最新候補を確認して、要約と会話のきっかけをそれぞれ合否入力できます。作成された候補は
承認待ちで止まり、LINEへ自動送信されません。集計は既定で
`data/vrt-audio-evaluation-report.json`へ保存します。
レポートには音声、文字起こし、ファイルパス、人物名、ジョブID、記録IDを含めません。

マニフェストの`acceptance`には、処理完了率、話者数・候補判定・分類・人手確認の最低精度と、処理時間の上限を
設定できます。すべての基準を満たすと終了コード0、満たさない場合は終了コード2になります。
生成文の基準を設定したマニフェストでは`--interactive-review`が必須です。`expected_category`は
候補が必要なケースで`growth`または`injury`、候補が不要なケースでは`null`にします。

話者数は生体情報や声紋ではなく、その音声内だけの匿名集計値として音声処理ジョブへ保存します。
話者分離が無効な環境では人数が未計測となり、期待値との照合は不合格になります。

### 火曜日のVRT切替

Macでの開発中は、これまでどおり次だけを使います。GPUワーカーは起動しないため、Mac用の設定や音声テストを変える必要はありません。

```bash
docker compose up --build
```

VRTを借りられたら、このリポジトリと `.env` をVRTへ置き、VRT上の `.env`
だけで次を有効にします。`.env` はGitへ追加しません。

```dotenv
APP_ENV=production
# 空のPostgreSQLなら、VRT起動時に移行ファイルから表を作成します。
DATABASE_URL=postgresql+psycopg://<DB接続ユーザー>:<DBパスワード>@<DBホスト>:5432/<DB名>
CLOUD_AUDIO_ENABLED=true
CLOUD_AUDIO_JOB_DIR=/var/lib/small-step/cloud-audio-jobs
EDGE_AUDIO_DEVICE=cuda
EDGE_AUDIO_COMPUTE_TYPE=float16
SPEAKER_DIARIZATION_DEVICE=cuda

# VRT上のvLLMコンテナへ、同じDocker内部ネットワークから接続します。
LLM_BACKEND=vllm
LLM_BASE_URL=http://small-step-vllm:8000/v1
LLM_ALLOW_EXTERNAL=true
LLM_MODEL=Qwen/Qwen3-32B

# Composeが管理するvLLMのキャッシュ先。既存のNVMeキャッシュを再利用します。
VLLM_MODEL_CACHE_DIR=/mnt/small-step-cache/huggingface
VLLM_COMPILE_CACHE_DIR=/mnt/small-step-cache/vllm
```

`LLM_ALLOW_EXTERNAL=true` は、ここではDockerサービス名を許可するために必要です。
LLMをインターネットへ公開する設定ではありません。ComposeがQwen3-32BのvLLMも管理し、
ホスト側ポートは`127.0.0.1:8001:8000`だけに限定します。`small-step-vllm` と
`gpu-worker`だけを`small-step-ai`ネットワークへ接続します。ネットワークが未作成の場合だけ、
起動前に作成します。

```bash
sudo docker network inspect small-step-ai >/dev/null 2>&1 \
  || sudo docker network create small-step-ai
```

以前の手動`docker run`で`small-step-vllm`を起動しているVRTでは、最初の切り替え時だけ
そのコンテナを削除します。モデルはNVMe側に残るため再ダウンロードされません。

```bash
sudo docker stop small-step-vllm
sudo docker rm small-step-vllm
```

次でデータベース準備・vLLM・API・GPUワーカーを一緒に起動できます。`compose.vrt.yaml`
はMacでは使いません。空のDBでは`migrate`が初期構成を適用し、vLLMとAPIがHealthyになってから各ワーカーが順番に起動します。Qwenの読込中は数分待ちます。

```bash
docker compose -f compose.yaml -f compose.vrt.yaml config
docker compose -f compose.yaml -f compose.vrt.yaml up -d --build
docker compose -f compose.yaml -f compose.vrt.yaml ps
```

APIのホスト側ポートは安全な初期値として `127.0.0.1:8000` にだけ公開されます。
外部端末から接続する前に、認証を有効化し、HTTPSのリバースプロキシを経由させてください。
検証のために `8000` 番ポートをインターネットへ直接公開しないでください。

`migrate`が`exited (0)`、`api`が`healthy`になったことを確認してください。`gpu-worker`は`api`が`healthy`になるまで待ってから起動します。`migrate`が止まった場合は、次で理由を確認してから対応します。データを消して再実行する必要はありません。

```bash
docker compose -f compose.yaml -f compose.vrt.yaml logs --tail=100 migrate
```

`api`のDockerヘルスチェックは、データベースへ接続してAPIが応答できることだけを確認します。GPU・LINEワーカーがAPIの起動を待つ一方、運用準備チェックがワーカーを待つ循環を避けるためです。移行状態、一時音声保存、文章生成AI、GPUワーカー、LINE設定とLINE送信ワーカーを含む確認結果は、次で見られます。

```bash
python scripts/check_runtime_readiness.py
```

`ready` 以外の場合は、そのVRTへ録音端末を切り替えずに `.env` と `migrate`
のログを見直します。LINE配信設定は表示のみで、LINEをまだ接続していない開発・検証環境では
`false` でもAPIは起動できます。

先生管理者は先生画面の「稼働準備」からも、同じ安全な確認結果を見られます。VRTをまだ使わない間は「Macでローカル処理中」と表示されます。VRTへ切り替えた後は、データベース更新、一時音声保存、文章生成AI、GPU音声処理、LINE配信設定、LINE送信処理の状態を、接続先やキーを表示せずに確認できます。

`APP_ENV=production`で起動する場合は、誤ってローカル開発設定を公開しないように、`AUTH_MODE=supabase`、Supabaseの公開設定、SQLite以外の`DATABASE_URL`が必須です。保護者用配信アーカイブを有効にする場合は、`GUARDIAN_ARCHIVE_BASE_URL`もHTTPS
URLでなければ起動しません。

`gpu-worker`のログに音声本文や元ファイル名は出力されません。稼働確認は次で行います。

```bash
docker compose -f compose.yaml -f compose.vrt.yaml logs --tail=100 gpu-worker
```

### LINE送信失敗の確認と再送

LINE配信ワーカーは、通信断などで送信結果が確定しない通知を勝手に繰り返し送信しません。二重送信を避けるため、失敗した場合は先生管理者が先生画面の「通知状況」で確認してから「再送を予約」を実行します。

通知一覧には送信試行回数と最終試行日時、本文やLINEの応答内容を含まない大まかな失敗区分だけが表示されます。保護者のLINE連携、ネットワーク、LINE側の一時的な障害、LINE設定のどれを確認すべきか判断するための情報です。

AIが返した信頼度が70%未満の記録候補は削除せず、レビュー一覧と詳細画面で「要確認」として強調します。承認確認にも注意文を表示するため、聞き取りづらい音声を保護者へそのまま配信することを防ぎつつ、実際の出来事を見逃さない設計です。

### GPU環境の準備

音声機能を動かす端末でだけ、追加パッケージを入れます。今のFastAPI・LINE動作には不要です。

```bash
.venv313/bin/python -m pip install -e '.[edge-audio]'
mkdir -p data/edge-audio-inbox
```

`.env`
には、ローカルLLMのOpenAI互換エンドポイントと、端末専用APIキーを設定します。Sakura高火力VRTでvLLMを同じVMに置く場合は、LLMを
`127.0.0.1` にだけ待ち受けさせます。

```dotenv
EDGE_AUDIO_INBOX_DIR=./data/edge-audio-inbox
EDGE_AUDIO_DEVICE=cuda
EDGE_AUDIO_COMPUTE_TYPE=float16
LLM_BACKEND=vllm
LLM_BASE_URL=http://127.0.0.1:8001/v1
LLM_MODEL=Qwen/Qwen3-32B
LLM_ALLOW_EXTERNAL=false
EDGE_API_URL=http://127.0.0.1:8000
EDGE_API_KEY=<POST /api/v1/edge-devices で発行した端末専用キー>
```

### Macで音声を自動送信するテスト

録音端末を用意する前に、Macを端末の代わりにできます。別の録音アプリなどで作成した対応形式の音声を
`data/edge-audio-inbox`
に置くと、Mac内で文字起こし・匿名化し、具体的な出来事がある場合だけ承認待ち記録として送信します。生音声や文字起こしはAPI・DBへ送信されません。

最初は、既存の音声を一度だけ処理する `--once`
を使います。話者識別はまだ作らないため、園児は音声内容やファイル名から推測しません。園児IDを省略すると、先生が確認画面で対象園児を選べます。

```bash
.venv313/bin/python scripts/watch_edge_audio.py --once
```

特定の園児に紐付けたテストを行う場合だけ、園児作成時に取得したIDを明示します。

```bash
.venv313/bin/python scripts/watch_edge_audio.py --child-id <園児ID> --once
```

確認できたら、次でフォルダを常時監視します。録音が終わったファイルは、作成から2秒以上経過してから処理するため、書き込み途中のファイルを避けられます。停止は
`Control+C` です。

```bash
.venv313/bin/python scripts/watch_edge_audio.py
```

監視間隔と待機秒数は `.env` の `EDGE_AUDIO_WATCH_POLL_SECONDS` と
`EDGE_AUDIO_WATCH_MIN_AGE_SECONDS`
で変更できます。既定では、処理を始めた音声は成功・失敗にかかわらず削除されます。

### Macのマイクから自動で録音するテスト

Macでは `ffmpeg`
を使って、マイクの音声を30秒ごとのWAVファイルとしてローカル受信フォルダへ保存できます。録音中は隠し一時ファイルを使い、録音が完了してから監視プログラムへ渡すため、途中の音声は処理されません。

最初に、Macで使える音声入力の番号を確認します。`Audio devices`
の一覧にある番号を控えてください。

```bash
.venv313/bin/python scripts/record_edge_audio.py --list-devices
```

別ターミナルで音声監視を起動した状態で、まず10秒の録音を1回だけ作成します。音声入力が一覧の
`0` なら `:0` のままで大丈夫です。

```bash
.venv313/bin/python scripts/watch_edge_audio.py
.venv313/bin/python scripts/record_edge_audio.py --once --chunk-seconds 10 --audio-device :0
```

初回はmacOSからターミナルのマイク利用許可を求められます。許可後、録音・匿名化・承認待ち記録の作成が順に行われます。通常運用では
`--once` を外します。録音秒数と既定の入力は `.env` の
`EDGE_AUDIO_RECORD_CHUNK_SECONDS` と `EDGE_AUDIO_INPUT_DEVICE` で変更できます。

### 匿名の話者分離

話者分離は、生音声を処理端末内で `speaker_01`
のような匿名の話者区間に分ける機能です。先生・園児の名前を判定せず、音声・文字起こし・話者区間をAPIやDBへ送信しません。

ローカルで動かす Community-1 モデルは、最初にHugging
Faceで利用条件へ同意し、無料のアクセストークンを作る必要があります。トークンを
`.env` の `SPEAKER_DIARIZATION_TOKEN`
に保存してから、音声処理用環境へ追加パッケージを入れます。

```bash
.venv313/bin/python -m pip install -e '.[speaker-diarization]'
```

`SPEAKER_DIARIZATION_TOKEN`
が設定されていると、通常のローカル処理とVRT処理でも自動的に匿名話者分離を行います。Whisperの単語時刻を匿名区間へ対応付け、匿名ラベル付きの文字起こしだけをQwenへ渡します。トークンが未設定なら話者分離だけを省略し、従来どおり文字起こしを続けます。

音声は `EDGE_AUDIO_INBOX_DIR`
に置いたまま、次のコマンドで話者数と匿名区間だけを単体確認できます。音声ファイル名に個人名を入れないでください。

```bash
.venv313/bin/python scripts/diarize_edge_audio.py data/edge-audio-inbox/<音声ファイル名>.wav
```

最初の分離で話者が1人だけと判定された場合は、既定で元音声を変更しない一時的な音量差補正をかけ、静かな話者を検出できるか1回だけ再確認します。補正後に十分な長さの別話者が見つかったときだけ結果を採用し、一時音声は直後に削除されます。マイクに届かなかった発話や大きな雑音に埋もれた発話を復元する機能ではありません。無効にする場合は
`.env` に `SPEAKER_DIARIZATION_LOW_VOLUME_RETRY=false` を設定してください。

声量差のある録音を試すときは、同意済みの成人2人が交互に話し、1人は少し小さめの声で話します。出力の読み方は次のとおりです。

```text
匿名の話者数: 2
音量差を補正して再確認した話者数: 2
補正後の結果を採用しています。
```

この場合は、最初の結果で見つからなかった静かな話者を補正後に検出できています。補正前後ともに話者数が
`1`
の場合は、静かな声がマイクに十分届いていない可能性があります。話者数を無理に増やさず、マイクを会話の中央に近づけるか、実機マイクで録音し直してください。

話者ラベルは、会話の交代をQwenが理解するためだけに使います。ラベル自体や話者区間は通知・成長記録・DBに保存しません。

録音時点で園児IDが指定されている場合は、同じ園児の直近5件の承認済み・配信済み記録も匿名の参考情報としてQwenへ渡します。現在の音声と過去記録の両方に根拠がある場合だけ、小さな変化を候補文へ含めます。園児未選択、未承認記録、別の園児の履歴は参照しません。

### 声紋の登録と本人確認

声紋機能は既定で無効です。VRT管理者が必要な設定を有効にした園では、先生が先生画面の「声紋設定」で次を自分で確認して同意します。

- 利用目的は声紋の登録・本人確認であること（録音内の先生照合は別の任意同意）
- 同意の有効期限（1〜365日）
- いつでも同意を取り消せること

同意後、先生本人がブラウザの録音ボタンで10〜15秒の音声を3回録音します。GPUワーカーは各回について録音時間、発話時間、声量、雑音、音割れ、複数話者を確認し、品質基準を満たさない場合は該当回の再録音を案内します。3回分の特徴量を平均し、暗号化した代表声紋だけを先生ごとに1件保存します。個別特徴量は平均化後すぐメモリから消去し、元音声も成功・失敗にかかわらず処理後に削除します。マイク録音に対応していない端末では3件の音声ファイルも選択できます。本人確認は10〜15秒の音声1回と保存済み代表声紋との1対1照合であり、先生のログインを置き換えるものではありません。

先生は同じ画面から再登録、本人確認、削除ができます。同意の取消または先生アカウントの利用停止時には、登録済み特徴量、処理ジョブ、残っている一時音声を削除します。通常の業務DBバックアップには声紋特徴量と照合ジョブの行を含めません。

VRTで有効にする場合は、`.env` に次を設定して `api` と `gpu-worker`
を再作成します。暗号鍵はGitへ追加せず、紛失すると登録済み声紋を復号できないため、秘密情報として安全に保管してください。

```bash
VOICEPRINT_ENABLED=true
VOICEPRINT_ENCRYPTION_KEY=<Fernet形式の秘密鍵>
VOICEPRINT_MODEL=pyannote/embedding
VOICEPRINT_MATCH_THRESHOLD=0.75
```

暗号鍵は次で生成できます。声紋機能には `CLOUD_AUDIO_ENABLED=true` と
`SPEAKER_DIARIZATION_TOKEN` も必要です。

```bash
python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

#### 録音からの担当候補

`/rec/` の連続録音・手動録音は、`RECORDER_VOICEPRINT_MATCHING_ENABLED=true`
で登録声紋と照合できます。 `RECORDER_ENABLED=true`、`VOICEPRINT_ENABLED=true`
も必要です。先生本人が「声紋設定」で
「同じ園の録音から私の声を照合し、担当候補を表示する」を選び、同意を更新してください。
既存の同意は自動的に照合へ転用しません。有効な登録声紋があれば追加同意だけで利用でき、再登録は不要です。

同じ園の有効・同意済み・同じモデルの声紋だけを照合し、話者ごとの重なっていない発話を3〜10秒、
最大8話者までメモリで扱います。短い・小さい・音割れした発話は使いません。
一致基準は `RECORDER_VOICEPRINT_MATCH_THRESHOLD=0.85`、次点との差は
`RECORDER_VOICEPRINT_MATCH_MARGIN=0.1`
が初期値です。類似度は本人である確率ではなく、
本番利用前に同意した先生の実音声で誤一致・見逃しを評価して調整してください。
複数の先生に一致、曖昧な一致、照合失敗、一部音声処理失敗では「先生未特定」とします。

記録詳細に担当候補を表示しますが、録音内の話者と記録の責任者は同じとは限りません。
実際の担当はログインした先生のままです。管理者が候補を引き継ぎ先に選び、既存の「担当を変更」で
確認すると引き継ぎます。承認・LINE配信も引き続き先生の操作が必要です。
一時特徴量は処理直後に消去し、録音音声は従来どおり処理後に削除します。候補の先生IDと実施有無だけを
記録へ保持し、類似度・話者ラベル・区間・特徴量は保存しません。候補情報は通常の記録バックアップに含まれます。
照合の追加同意を外す、同意取消、声紋削除・再登録、利用停止、同意・声紋の期限後の清掃で既存候補も削除します。
表示時にも同意・期限・園を再確認します。登録声紋のないバックアップ復元先には候補を表示しません。

Ubuntuへの反映は、新コード取得、`api migrate gpu-worker` のビルド、`migrate`
による `0025_recorder_voiceprint`
の適用、上記設定追加後のAPI・GPUワーカー再作成の順で行います。
この追加照合はESP端末の音声ジョブにはまだ適用しません。

MCPホストが同じPC上で起動する場合は、標準入出力で起動します。

```bash
.venv313/bin/python -m app.mcp_server
```

別プロセスのMCPクライアントから接続するだけなら、ローカルHTTPにもできます。外部ネットワークへは公開しません。

```bash
.venv313/bin/python -m app.mcp_server --streamable-http --port 8002
```

接続先は `http://127.0.0.1:8002/mcp` です。

## ローカルで起動

Python 3.11以上を使います。

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload
```

API仕様は起動後に `http://127.0.0.1:8000/docs` で確認できます。

バックエンドの route を追加・変更した場合は、起動中の FastAPI
を再起動してください。 サイドパネルに想定したバッジが出ない場合、0
件なら非表示が正常です。件数があるはずなのに出ない場合は、 認証済みの
`GET /api/v1/navigation-badges?school_id=<園ID>` が 200 を返すことを確認します。
404 なら古いプロセスが動いている可能性があります。Supabase Auth モードでは、401
なら token の有効期限を、 503 で `Supabase Auth could not be reached`
と出る場合は API から Supabase Auth への接続を確認してください。
バッジ取得の失敗は画面全体を停止させず、バッジだけを隠します。

バックエンドのテスト:

```bash
pytest
```

SvelteKit
の開発・テスト・ビルドは「[フロントエンド開発](#フロントエンド開発)」を参照してください。

## Supabase Authを有効にする

先生Web画面（将来のFlutterアプリも同じ方式）がSupabaseへ直接メール・パスワードでログインし、取得したアクセストークンをこのAPIへ
`Authorization: Bearer <access_token>` として送ります。API側はSupabase Authの
`/auth/v1/user`
でトークンを検証するため、JWTの署名方式を個別に設定する必要はありません。

### Supabase Dashboardでの設定

1. Freeプロジェクトを作成する。
2. `Authentication > Providers > Email` でメール認証と `Confirm Email`
   を有効にする。
3. `Authentication > General Configuration` で `Allow new users to sign up`
   を無効にする。これにより、招待済みの先生だけがログインできる。
4. `Project Settings > API Keys` からProject URLと**Publishable
   key**を取得する。`service_role` / secret
   keyは先生Web画面にもこのAPIにも設定しない。
5. 最初の管理者ユーザーを `Authentication > Users > Add user > Send invitation`
   から招待する。

### APIの設定

`.env` を次のように設定して再起動します。`SUPABASE_BOOTSTRAP_ADMIN_EMAILS`
は、最初に先生管理者として登録できるメールアドレスです。

```dotenv
AUTH_MODE=supabase
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
SUPABASE_BOOTSTRAP_ADMIN_EMAILS=admin@example.com
```

### 既存の園を使う初回ログイン

すでにローカルDBに園を登録している場合は、`http://127.0.0.1:8000/teacher/`
を開き、最初の管理者のメールアドレスとパスワードでログインします。最初の一度だけ「管理する園」と表示名を選ぶ画面が出るので、運用する園を選んで登録します。この操作で、そのSupabaseアカウントが選択した園の
`school_admin` として紐付きます。

新規の園から始める場合は、管理者のアクセストークンで `POST /api/v1/schools`
を実行すると、園と管理者先生アカウントが同時に作成されます。

最初の園と管理者を作るだけなら、次の補助スクリプトが使えます。メールアドレス・パスワードは画面に表示されません。

```bash
.venv/bin/python scripts/bootstrap_admin.py
```

初回設定が終わったら、`.env` の `SUPABASE_BOOTSTRAP_ADMIN_EMAILS`
を空にして保存し、FastAPIを再起動してください。以後は、管理者として登録された先生だけが園の管理操作を行えます。

以後の先生追加は次の順です。

1. 管理者トークンで `POST /api/v1/teachers`
   を実行し、先生のメールアドレスを事前登録する。
2. 招待送信を設定済みなら先生管理画面からその先生へ招待を送る。未設定の場合はSupabase
   Dashboardから送る。
3. 先生がパスワード設定後に `http://127.0.0.1:8000/teacher/`
   からログインする。画面が自動で `POST /api/v1/auth/link-teacher`
   を一度だけ呼ぶ。
4. 以後は、画面が付与するアクセストークンで自分の園のデータだけへアクセスできる。

`GET /api/v1/auth/me`
で、現在のSupabaseユーザーと紐付いた先生プロフィールを取得できます。

### Flutter側のログイン例

Flutterには `supabase_flutter` を追加し、ログイン成功後の `session.accessToken`
をFastAPIへのリクエストに付与します。

```dart
final response = await Supabase.instance.client.auth.signInWithPassword(
  email: email,
  password: password,
);
final token = response.session!.accessToken;
// FastAPIへ: Authorization: Bearer $token
```

## Dockerで起動

Docker
Composeでは、デフォルトで永続ボリューム上のSQLiteを使います。早い試作に使えます。

```bash
cp .env.example .env
docker compose up --build
```

本番では `DATABASE_URL` をSupabase
PostgreSQLなどの永続DBに設定します。また、上記のSupabase
Auth設定を有効にしてください。

## データベースの更新

ローカル開発用のSQLiteは、これまでどおり起動時に自動準備されます。本番用のPostgreSQLでは、表の作成や変更をAPI起動時に自動で行いません。代わりに、Gitで確認できるAlembic移行ファイルを適用します。

新しい空のPostgreSQLを使う前、またはVRTへ初回配置する前には、次を一度だけ実行します。接続先やパスワードは`.env`からだけ読み取り、表示しません。

```bash
python scripts/prepare_database.py
```

既存のローカルSQLiteデータベースでは、同じコマンドが現在の構成を確認して移行管理に登録します。既に表があるPostgreSQLに対しては、安全のため自動登録を行わず停止します。バックアップを確認したうえで、データ移行の手順を個別に判断してください。

今後データベース構成を変更するときは、新しいAlembic移行ファイルを追加してからVRTへ反映します。既存の移行ファイルは書き換えません。

## LINE Messaging APIを接続する

このバックエンドは、LINEのWebhook署名を検証し、先生が承認した通知を保護者へpush送信できます。Webhook受信時には保護者のメッセージ本文を保存しません。

1. LINE Developers ConsoleでMessaging APIチャネルを作成する。
2. チャネルの**Channel secret**と**Channel access token**を取得する。
3. `.env` に次を設定する。値はGitへcommitしない。

```dotenv
LINE_CHANNEL_SECRET=...
LINE_CHANNEL_ACCESS_TOKEN=...
```

4. HTTPSで公開したAPIへ、Webhook URLとして次を設定する。

```text
https://your-api.example.com/api/v1/line/webhook
```

LINE Developers
Consoleの`Verify`は、署名付きでイベントなしのリクエストを送ります。このAPIは正しい署名ならHTTP
200を返します。

送信予定時刻を過ぎた承認済み通知は、次のワーカーで配信します。`--dry-run`では
LINE へ送信せず対象件数を確認できますが、 送信先が未連携の期限到来通知は
`failed`
に更新されるため、完全な読み取り専用ではありません。通常の1回実行では、失敗した通知を自動で再送しません。

```bash
python scripts/send_pending_line_notifications.py --dry-run
python scripts/send_pending_line_notifications.py
```

VRTなどの常時稼働環境では、次のように`--watch`を付けると、既定で15秒ごとに送信待ちを確認します。間隔は`LINE_WORKER_POLL_SECONDS`で変更できます。アクセストークンが未設定の場合、通知を失敗扱いにせず起動を停止します。

```bash
python scripts/send_pending_line_notifications.py --watch
```

送信に失敗した通知は、先生用画面の「通知状況」で内容を確認してから「再送を予約」を選べます。通知は送信待ちへ戻り、LINE送信ワーカーが配信します。サーバー運用者が明示的に再試行するときは、次も使えます。

```bash
python scripts/send_pending_line_notifications.py --retry-failed
```

送信待ちの通知は、学校管理者が先生用画面の「日時を変更」から未来の配信時刻へ変更できます。変更後もLINE送信ワーカーは新しい時刻まで送信しません。誤送信を止める必要がある場合は「配信を取消」を使えます。取消後も運用履歴は残りますが、LINE送信ワーカーはその通知を送信しません。すでにLINEへ送信済み、または送信失敗となった通知は日時変更・取消ができないため、内容を確認してから必要に応じて再送を予約してください。

Docker Composeでは、次のように実行できます。

```bash
docker compose run --rm api python scripts/send_pending_line_notifications.py --dry-run
```

保護者のLINEユーザーIDは `children.guardian_line_user_id`
に保存されます。LINEアカウントと園児は、次の招待コード方式で紐付けます。

### 保護者のLINEアカウントを園児へ紐付ける

先生は `POST /api/v1/line/link-invitations`
へ園児IDを指定して、期限付きの招待コードを発行します。返される `invite_code`
は一度だけ保護者へ渡し、保護者はLINE公式アカウントのトークへコードだけを送信します。

```json
{
  "child_id": "<child UUID>",
  "expires_in_minutes": 30
}
```

コードはDBへ平文保存せず、発行時の応答にだけ含まれます。先生画面では、コードを表示せずに「招待済み」と有効期限だけを確認できます。コードを紛失した場合は新しいコードを発行し、過去の未使用コードを即時失効させます。Webhookは紐付けに必要なLINEユーザーIDだけを保存し、保護者のメッセージ本文は保存しません。

### Supabase PostgreSQL へ接続する

FreeプランでローカルPCやIPv4のサーバーから接続するときは、Supabase Dashboard の
**Connect → Direct → Session pooler** を選びます。表示された URI
はチャットに貼り付けず、ローカルで次を実行してください。

Small StepはSupabaseのData
APIから業務テーブルを直接操作しません。PostgreSQL向けの移行では、`public`スキーマの業務テーブルでRLSを有効化し、ブラウザ用の`anon`・`authenticated`ロールから直接操作権限を外します。先生Web画面はSupabase
Authでログインし、業務データは認証済みのFastAPIだけを経由します。

```bash
.venv/bin/python -m pip install "psycopg[binary]>=3.2.0"
.venv/bin/python scripts/configure_supabase_database.py
.venv/bin/python scripts/migrate_sqlite_to_supabase.py
```

スクリプトの最初の入力には、ダッシュボードにある `[YOUR-PASSWORD]`
を含む接続文字列を貼り付けます。次の2回の入力には、プロジェクト作成時に決めた**データベース用パスワード**を入力します（Supabaseへのログイン用パスワードとは別です）。パスワードは画面に表示されず、`.env`
以外には保存されません。

最後の移行スクリプトは、ローカルSQLiteに作成済みの園・先生・園児・記録に加え、録音端末、音声処理ジョブ、同意、監査履歴、LINE連携を含む全アプリケーションデータをSupabaseへ一度だけコピーします。Supabase側にデータがある場合は安全のため中止し、上書きしません。

### 実ログインの確認

Supabaseのメールアドレス・パスワードで、管理者認証まで通るかを確認できます。アクセストークンやパスワードは表示・保存されません。

```bash
.venv/bin/python scripts/verify_supabase_login.py
```

### 承認フローのテスト

管理者としてログインしてから、明示的にテストと分かる園児・成長記録を1件作成し、承認後に通知待ちになるところまでを確認できます。再実行しても同じテストデータを再利用します。

```bash
.venv/bin/python scripts/create_demo_growth_record.py
```

### 端末用APIキーの登録

先生のログイン情報を端末へ置かず、胸元マイクや園内エッジPCに専用キーを発行します。キーは作成・再発行時に一度だけ表示され、サーバーにはハッシュ値だけが保存されます。

```bash
.venv/bin/python scripts/register_edge_device.py
```

端末からは `X-Edge-Api-Key` ヘッダーで `POST /api/v1/edge/records`
を呼びます。このAPIは園・担当先生をキーから判断し、`raw_audio`
のような未定義項目を受け付けません。

キーの有効性だけを確認するときは、データを書き込まない次のコマンドを使います。

```bash
.venv/bin/python scripts/verify_edge_device.py
```

ESP32-S3とEV_INMP621-FXを使う実機ファームウェア、配線、秘密値の設定、書き込み手順は
[`firmware/esp32-s3-recorder/README.md`](firmware/esp32-s3-recorder/README.md)
にあります。
通信切断・混雑・サーバー障害のときは同じアップロードIDで1件を再送するため、VRT側の重複防止と組み合わせて二重登録を避けます。無効な端末キーなど、再送しても直らないHTTP
`4xx`では音声を端末から削除し、設定ミスで新しい録音が止まり続けないようにします。

起動中の開発APIへ、端末の立場で匿名化済みのテスト候補を送るには次を使います。`【端末テスト】`
と明示した記録が作成され、先生の承認待ちになります。

```bash
.venv/bin/python scripts/send_demo_from_edge.py
```

その候補を管理者として承認し、通知待ちを確認するには次を実行します。

```bash
.venv/bin/python scripts/approve_latest_edge_demo.py
```

## さくらの高火力 VRTへの載せ方

高火力
VRTはGPU搭載のVMです。API自体はGPUを使わないため、通常のAPIコンテナとGPU使用の
`gpu-worker`（Whisper・ローカルLLM）を分けています。VRTでは `compose.vrt.yaml`
を重ねて、同じ非公開ボリュームを共有します。

1. VMにDocker EngineとDocker Composeを導入する。
2. このリポジトリをVMへ配置し、`.env` に`APP_ENV=production`、本番の
   `DATABASE_URL`、Supabase Auth設定を入れる。
3. `docker compose -f compose.yaml -f compose.vrt.yaml up -d --build`
   で、データベース準備・API・GPUワーカー・LINE配信ワーカーを起動する。空のDBには初期移行が自動適用される。LINE配信ワーカーには`LINE_CHANNEL_ACCESS_TOKEN`が必要です。
4. リバースプロキシ（CaddyまたはNginx）でTLS終端し、APIの8000番ポートをインターネットへ直接公開しない。
5. GPUワーカーを追加する際は、モデル・一時音声は永続ディスクまたは園内側に置く。高火力
   VRTの一時領域はVM停止・障害時に消えるため、そこを永続データの保存先にしない。

## Supabase PostgreSQLのバックアップと復元確認

Supabaseのバックアップ提供範囲はプランによって異なります。Freeプランでは、公式ドキュメントも
定期的なデータ出力と外部保管を案内しています。最新条件は
[SupabaseのDatabase Backups](https://supabase.com/docs/guides/platform/backups)を確認してください。

このリポジトリのバックアップは、Small
Stepが使う`public`スキーマをPostgreSQLのカスタム形式で
保存します。作成直後に必要テーブル、アーカイブ構造、SHA-256チェックサムを検証し、途中で失敗した
ファイルは正式なバックアップとして残しません。バックアップには園児名、通知文、LINE連携情報などの
個人データが含まれるため、保存先ディレクトリは`0700`、ファイルは`0600`に制限されます。

バックアップ専用イメージを作り、業務データを1回保存します。APIやGPUワーカーは停止しません。

```bash
cd /home/ubuntu/small-step

sudo docker compose \
  -f compose.yaml \
  -f compose.vrt.yaml \
  --profile operations \
  build database-tools

sudo docker compose \
  -f compose.yaml \
  -f compose.vrt.yaml \
  --profile operations \
  run --rm database-tools
```

手動確認に成功したら、`.env`の`DATABASE_BACKUP_TIME`へ毎日の作成時刻を設定し、日次ワーカーを
起動します。既定は日本時間の03:00です。起動時に当日分がなければ予定時刻を待たずに1件作成し、
失敗した場合は既定で5分後に再試行します。API、GPU、LINE処理は停止しません。

```bash
sudo docker compose \
  -f compose.yaml \
  -f compose.vrt.yaml \
  --profile backup \
  up -d --build backup-worker

sudo docker compose \
  -f compose.yaml \
  -f compose.vrt.yaml \
  --profile backup \
  ps backup-worker
```

`DATABASE_BACKUP_RETENTION_COUNT=0`は自動削除なしです。後述の外部保管を有効にするまでは`0`を維持して
ください。外部保管を有効にすると、日次ワーカーは「作成・検証、公開鍵暗号化、外部アップロード、外部の
サイズと検証値の確認」のすべてに成功してから古いローカル世代を削除します。外部保存に失敗した日は、
新しいローカルバックアップを残したまま再試行し、過去世代を削除しません。

保存先は既定でホストの`./data/database-backups`です。変更するときだけ`.env`の
`DATABASE_BACKUP_HOST_DIR`へ絶対パスを設定します。NVMeのモデルキャッシュ領域は、障害時に
同時に失う可能性があるため指定しないでください。

最新バックアップのチェックサムと構成だけを再確認する場合は次を使います。

```bash
sudo docker compose \
  -f compose.yaml \
  -f compose.vrt.yaml \
  --profile operations \
  run --rm database-tools \
  python scripts/verify_database_backup.py
```

実際に復元できることは、ネットワーク非公開かつメモリ上だけで動く使い捨てPostgreSQLで確認します。
復元スクリプトは、本番と同じ接続先や外部ホストを復元先として受け付けません。復元先に業務テーブルが
ないことを確認してから、PostgreSQLが既定で作る空の`public`スキーマをアーカイブ内の構成へ置き換えます。

```bash
sudo docker compose \
  -f compose.yaml \
  -f compose.vrt.yaml \
  --profile recovery \
  up -d --wait restore-db

sudo docker compose \
  -f compose.yaml \
  -f compose.vrt.yaml \
  --profile operations \
  --profile recovery \
  run --rm database-tools \
  python scripts/rehearse_database_restore.py

sudo docker compose \
  -f compose.yaml \
  -f compose.vrt.yaml \
  --profile recovery \
  rm -sf restore-db
```

このアーカイブに音声ファイル、Supabase Authのユーザー、Supabase
Storageのオブジェクトは含まれません。
それらを含むプロジェクト全体の復旧はSupabase側のバックアップ方針と合わせて管理してください。また、
VRT内に1部あるだけではVRT障害への備えにならないため、作成後は暗号化された外部保管先へ複製します。
復元リハーサルに成功したファイルだけを正式な世代として扱い、世代削除は外部保管を確認してから行います。

### 暗号化した外部バックアップ

VRTの故障や誤削除に備え、検証済みバックアップを`age`公開鍵で暗号化し、AWS
S3またはS3互換の非公開
バケットへ自動保存できます。VRTに置くのは暗号化用の公開Recipientだけです。復号用の秘密Identityは
VRT、Git、チャットへ置かず、管理責任者がオフラインで保管してください。S3のアクセスキーには対象
プレフィックスへのアップロードと確認に必要な最小権限だけを与え、削除権限は与えません。

まず安全な別端末で鍵を作ります。表示された`age1...`だけをVRTで使い、`.agekey`ファイルはUSBメモリなど
別の安全な場所へ二重保管します。

```bash
umask 077
age-keygen -o small-step-backup.agekey
age-keygen -y small-step-backup.agekey
```

VRTの`.env`へ次を設定します。AWS
S3では`DATABASE_BACKUP_S3_ENDPOINT_URL`を空にします。S3互換サービスでは
そのサービスのHTTPSエンドポイントを設定します。サービス側暗号化ヘッダーに非対応でも、`none`を選べば
`age`による端末側暗号化は維持されます。

```dotenv
DATABASE_BACKUP_OFFSITE_ENABLED=true
DATABASE_BACKUP_AGE_RECIPIENT=age1から始まる公開Recipient
DATABASE_BACKUP_S3_BUCKET=非公開バケット名
DATABASE_BACKUP_S3_PREFIX=small-step/database
DATABASE_BACKUP_S3_ENDPOINT_URL=
DATABASE_BACKUP_S3_REGION=ap-northeast-1
DATABASE_BACKUP_S3_SSE=AES256
DATABASE_BACKUP_S3_KMS_KEY_ID=
AWS_ACCESS_KEY_ID=外部保存専用アクセスキー
AWS_SECRET_ACCESS_KEY=外部保存専用シークレット
```

自動削除を有効にする前に、最新の1件を手動で外部保存して確認します。成功すると外部オブジェクトの
サイズ、平文と暗号文のSHA-256、サービス側暗号化方式を確認し、個人情報を含まない確認状態を
`.small-step-offsite-backup.json`へ保存します。

```bash
sudo docker compose \
  -f compose.yaml \
  -f compose.vrt.yaml \
  --profile operations \
  build database-tools

sudo docker compose \
  -f compose.yaml \
  -f compose.vrt.yaml \
  --profile operations \
  run --rm database-tools \
  python scripts/upload_latest_database_backup.py
```

外部保存を有効にすると`operations-monitor`も、外部保存の欠落、最新世代との不一致、26時間以上の遅延を
検知してLINEへ知らせます。外部から復元するときは暗号化オブジェクトを安全な作業端末へダウンロードし、
保管していた秘密Identityで`age --decrypt`します。復号後は`pg_restore --list`と使い捨てDBへの復元
リハーサルを行ってから、本番復旧を判断してください。

Supabase AuthユーザーとSupabase
Storageは、この`public`スキーマのバックアップ対象外です。現在Small Stepの
音声はVRT内の短期保存で、Supabase
Storageは使用していません。Authを含むプロジェクト全体の障害には、
Supabase公式のDatabase
Backupsとプロジェクト復旧手順を併用します。`auth`や`storage`スキーマをこの
スクリプトで上書きすると認証を壊す可能性があるため、自動復元の対象にはしていません。

## VRTの障害をLINEで受け取る

`operations-monitor`はAPIとは別コンテナで動き、API、データベース更新、GPU音声処理、vLLM、LINE送信処理、
最新バックアップの更新時刻とチェックサム、保存領域の空き容量を1分ごとに確認します。園児名、音声、通知文、
URL、接続情報はLINE通知にも状態ファイルにも保存しません。

一時的な再起動で通知しないよう、同じ異常が既定で3分続いた場合だけ管理者へLINE通知します。同じ状態の
連続通知は6時間に1回までで、すべて正常に戻ると復旧通知を1回送ります。LINEへの送信結果が不明な場合は、
[LINE公式の再試行仕様](https://developers.line.biz/ja/docs/messaging-api/retrying-api-request/)に従い、
24時間の管理期限内は永続化した同じ再試行キーを使うため重複送信を抑えます。

VRTの`.env`へ次を設定します。`OPERATIONS_ALERT_LINE_USER_ID`は通知を受ける運用責任者本人のLINEユーザーIDで、
Gitへ追加したりチャットへ貼ったりしないでください。

```dotenv
OPERATIONS_MONITOR_ENABLED=true
OPERATIONS_ALERT_LINE_USER_ID=ここへ運用責任者のLINEユーザーID
```

最初にLINE送信なしで稼働状態を確認し、次に個人情報を含まないテスト通知を1回送ります。テスト通知が届き、
`運用監視: 正常`になれば常駐監視を起動できます。

```bash
sudo docker compose \
  -f compose.yaml \
  -f compose.vrt.yaml \
  --profile monitoring \
  run --rm --no-deps operations-monitor \
  python scripts/monitor_operations.py --dry-run

sudo docker compose \
  -f compose.yaml \
  -f compose.vrt.yaml \
  --profile monitoring \
  run --rm --no-deps operations-monitor \
  python scripts/monitor_operations.py --send-test-notification

sudo docker compose \
  -f compose.yaml \
  -f compose.vrt.yaml \
  --profile monitoring \
  up -d --build operations-monitor

sudo docker compose \
  -f compose.yaml \
  -f compose.vrt.yaml \
  --profile monitoring \
  ps operations-monitor
```

最新バックアップが26時間を超えると警告になるため、日次ワーカーが停止した場合も検知できます。監視自体が
VRT内で動く都合上、VRT全体の停止やインターネット回線断はLINEへ送れません。その範囲は次のGitHub
Actions 外部監視で補います。Quick
Tunnelでも利用できますが、URLが変わるたびにGitHub Secretの更新が必要です。

## VRT全体の停止を外部から検知する

`.github/workflows/external-vrt-monitor.yml`は、GitHub
Actionsから5分ごとに公開中の
`/api/v1/health`を3回確認します。APIとデータベースへ接続できない状態では専用のGitHub
Issueを1件だけ作成し、
復旧時にコメントを追加して閉じます。LINE用Secretも設定した場合は、最初の障害と復旧だけを運用責任者へ通知します。
同じ障害を確認し続けてもIssueを増やさず、LINEには同じ再試行キーを使います。

GitHubのリポジトリで `Settings` → `Secrets and variables` → `Actions`
を開き、次を登録します。

| 種類     | 名前                                  | 設定する値                                    |
| -------- | ------------------------------------- | --------------------------------------------- |
| Variable | `SMALL_STEP_EXTERNAL_MONITOR_ENABLED` | 準備完了後に `true`                           |
| Secret   | `SMALL_STEP_EXTERNAL_HEALTH_URL`      | `https://公開URL/api/v1/health`               |
| Secret   | `LINE_CHANNEL_ACCESS_TOKEN`           | VRT内部監視と同じLINEチャネルアクセストークン |
| Secret   | `OPERATIONS_ALERT_LINE_USER_ID`       | 通知を受ける運用責任者のLINEユーザーID        |

LINE用の2つのSecretを省略した場合もGitHub
Issueによる障害記録は動きます。片方だけを設定してはいけません。 Quick
Tunnelを使っている間は再起動のたびにURLが変わるため、`SMALL_STEP_EXTERNAL_HEALTH_URL`も直ちに更新します。
固定URLへ切り替えた後は、このSecretの変更だけで監視を継続できます。

有効化前に `Actions` → `Small Step external VRT monitor` → `Run workflow`
で手動実行します。 正常時に `外部監視: 正常` と表示されたらVariableを `true`
にします。監視先URL、LINEの秘密値、園児、音声は
Issueや実行ログへ出力しません。GitHub
Actionsの定期実行は数分遅れる場合があるため、これは即時フェイルオーバーではなく
VRT全体の停止を知らせる補助監視です。GPU・LINEワーカー・バックアップの詳細はVRT内の`operations-monitor`が確認します。

## コード反映後に残る実機・外部設定

1. 複数話者・雑音・声量差を含む匿名テストセットを収録し、設定済みの合格基準を満たすまで調整する
2. ESP32-S3録音端末を実機へ書き込み、PSRAM・マイク配線・無音しきい値・再送を確認する
3. GitHub Actionsの外部監視を実機確認し、Quick Tunnelから固定HTTPS
   URLへ切り替える
4. 外部バックアップ用の非公開S3バケットと`age`鍵を準備し、外部保存と復号リハーサルを実施する

>>>>>>> e6bd5d7a9b11dbb221ef31333fe67569010c7698
