# 認証・データベース・LINE・端末の初期設定

[README](../../README.md) / [デプロイ仕様](../architecture/deployment.md)

ローカルで画面を起動する手順はREADMEを参照してください。以下のコマンドはリポジトリのルートで実行します。
例の `.venv/bin/python` はmacOS/Linux用です。Windowsでは `.venv/Scripts/python.exe` を使います。
外部サービスの画面名・プラン・制限は変更されるため、導入時に公式資料と管理画面を確認します。

## Supabase Authを有効にする

先生Web画面がSupabaseへ直接メール・パスワードでログインし、取得したアクセストークンをこのAPIへ `Authorization: Bearer <access_token>` として送ります。API側はSupabase Authの `/auth/v1/user` でトークンを検証するため、JWTの署名方式を個別に設定する必要はありません。

### Supabase Dashboardでの設定

1. 利用するプロジェクトを作成する。
2. `Authentication > Providers > Email` でメール認証と `Confirm Email` を有効にする。
3. `Authentication > General Configuration` で `Allow new users to sign up` を無効にする。これにより、招待済みの先生だけがログインできる。
4. `Project Settings > API Keys` からProject URLと**Publishable key**を取得する。公開設定にはPublishable keyを使う。secret keyはブラウザへ渡さず、先生招待を有効にする場合だけサーバー側の `SUPABASE_SECRET_KEY` に設定する（[先生招待](../teacher-invitations.md)）。
5. 最初の管理者ユーザーを `Authentication > Users > Add user > Send invitation` から招待する。

### APIの設定

`.env` を次のように設定して再起動します。`SUPABASE_BOOTSTRAP_ADMIN_EMAILS` は、最初に先生管理者として登録できるメールアドレスです。

```dotenv
AUTH_MODE=supabase
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
SUPABASE_BOOTSTRAP_ADMIN_EMAILS=admin@example.com
```

### 既存の園を使う初回ログイン

すでにローカルDBに園を登録している場合は、`http://127.0.0.1:8000/teacher/` を開き、最初の管理者のメールアドレスとパスワードでログインします。最初の一度だけ「管理する園」と表示名を選ぶ画面が出るので、運用する園を選んで登録します。この操作で、そのSupabaseアカウントが選択した園の `school_admin` として紐付きます。

新規の園から始める場合は、管理者のアクセストークンで `POST /api/v1/schools` を実行すると、園と管理者先生アカウントが同時に作成されます。

最初の園と管理者を作るだけなら、次の補助スクリプトが使えます。メールアドレス・パスワードは画面に表示されません。

```bash
.venv/bin/python scripts/bootstrap_admin.py
```

初回設定が終わったら、`.env` の `SUPABASE_BOOTSTRAP_ADMIN_EMAILS` を空にして保存し、FastAPIを再起動してください。以後は、管理者として登録された先生だけが園の管理操作を行えます。

以後の先生追加は次の順です。

1. 管理者トークンで `POST /api/v1/teachers` を実行し、先生のメールアドレスを事前登録する。
2. 招待送信を設定済みなら先生管理画面からその先生へ招待を送る。未設定の場合はSupabase Dashboardから送る。
3. 先生がパスワード設定後に `http://127.0.0.1:8000/teacher/` からログインする。画面が自動で `POST /api/v1/auth/link-teacher` を一度だけ呼ぶ。
4. 以後は、画面が付与するアクセストークンで自分の園のデータだけへアクセスできる。

`GET /api/v1/auth/me` で、現在のSupabaseユーザーと紐付いた先生プロフィールを取得できます。

## Dockerで起動

Docker Composeでは、デフォルトで永続ボリューム上のSQLiteを使います。早い試作に使えます。

```bash
cp .env.example .env
docker compose up --build
```

本番では `DATABASE_URL` をSupabase PostgreSQLなどの永続DBに設定します。また、上記のSupabase Auth設定を有効にしてください。

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

LINE Developers Consoleの`Verify`は、署名付きでイベントなしのリクエストを送ります。このAPIは正しい署名ならHTTP 200を返します。

送信予定時刻を過ぎた承認済み通知は、次のワーカーで配信します。`--dry-run`では LINE へ送信せず対象件数を確認できますが、
送信先が未連携の期限到来通知は `failed` に更新されるため、完全な読み取り専用ではありません。通常の1回実行では、失敗した通知を自動で再送しません。

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

送信待ちの通知は、先生管理者が先生用画面の「日時を変更」から未来の配信時刻へ変更できます。変更後もLINE送信ワーカーは新しい時刻まで送信しません。誤送信を止める必要がある場合は「配信を取消」を使えます。取消後も運用履歴は残りますが、LINE送信ワーカーはその通知を送信しません。すでにLINEへ送信済み、または送信失敗となった通知は日時変更・取消ができないため、内容を確認してから必要に応じて再送を予約してください。

Docker Composeでは、次のように実行できます。

```bash
docker compose run --rm api python scripts/send_pending_line_notifications.py --dry-run
```

保護者のLINEユーザーIDは `children.guardian_line_user_id` に保存されます。LINEアカウントと園児は、次の招待コード方式で紐付けます。

### 保護者のLINEアカウントを園児へ紐付ける

先生管理者は `POST /api/v1/line/link-invitations` へ園児IDを指定して、期限付きの招待コードを発行します。返される `invite_code` は一度だけ保護者へ渡し、保護者はLINE公式アカウントのトークへコードだけを送信します。

```json
{
  "child_id": "<child UUID>",
  "expires_in_minutes": 30
}
```

コードはDBへ平文保存せず、発行時の応答にだけ含まれます。先生画面では、コードを表示せずに「招待済み」と有効期限だけを確認できます。コードを紛失した場合は新しいコードを発行し、過去の未使用コードを即時失効させます。Webhookは紐付けに必要なLINEユーザーIDだけを保存し、保護者のメッセージ本文は保存しません。

### Supabase PostgreSQL へ接続する

接続する端末のネットワークに合うPostgreSQL接続先をSupabase DashboardのConnectから選びます。IPv4環境ではSession poolerなど、接続可能な方式を確認します。表示された URI はチャットに貼り付けず、ローカルで次を実行してください。

Small StepはSupabaseのData APIから業務テーブルを直接操作しません。PostgreSQL向けの移行では、`public`スキーマの業務テーブルでRLSを有効化し、ブラウザ用の`anon`・`authenticated`ロールから直接操作権限を外します。先生Web画面はSupabase Authでログインし、業務データは認証済みのFastAPIだけを経由します。

```bash
.venv/bin/python -m pip install "psycopg[binary]>=3.2.0"
.venv/bin/python scripts/configure_supabase_database.py
.venv/bin/python scripts/migrate_sqlite_to_supabase.py
```

スクリプトの最初の入力には、ダッシュボードにある `[YOUR-PASSWORD]` を含む接続文字列を貼り付けます。次の2回の入力には、プロジェクト作成時に決めた**データベース用パスワード**を入力します（Supabaseへのログイン用パスワードとは別です）。パスワードは画面に表示されず、`.env` 以外には保存されません。

最後の移行スクリプトは、ローカルSQLiteに作成済みの園・先生・園児・記録に加え、録音端末、音声処理ジョブ、同意、監査履歴、LINE連携を含む全アプリケーションデータをSupabaseへ一度だけコピーします。Supabase側にデータがある場合は安全のため中止し、上書きしません。

### 実ログインの確認

Supabaseのメールアドレス・パスワードで、管理者認証まで通るかを確認できます。アクセストークンやパスワードは表示・保存されません。

```bash
.venv/bin/python scripts/verify_supabase_login.py
```

### 承認フローのテスト

管理者としてログインしてから、明示的にテストと分かる園児・成長記録を1件作成し、承認後の通知作成を確認します。このスクリプトは通知が送信キューに現れることを期待するため、試用園やLINE未連携では確認に失敗します。新規園の試用フラグをテストのために解除せず、試用園では画面で「試用承認済み（配信なし）」を確認してください。再実行しても同じテストデータを再利用します。

```bash
.venv/bin/python scripts/create_demo_growth_record.py
```

### 端末用APIキーの登録

先生のログイン情報を端末へ置かず、胸元マイクや園内エッジPCに専用キーを発行します。キーは作成・再発行時に一度だけ表示され、サーバーにはハッシュ値だけが保存されます。

```bash
.venv/bin/python scripts/register_edge_device.py
```

端末からは `X-Edge-Api-Key` ヘッダーで `POST /api/v1/edge/records` を呼びます。このAPIは園・担当先生をキーから判断し、`raw_audio` のような未定義項目を受け付けません。

キーの有効性だけを確認するときは、データを書き込まない次のコマンドを使います。

```bash
.venv/bin/python scripts/verify_edge_device.py
```

ESP32-S3とEV_INMP621-FXを使う実機ファームウェア、配線、秘密値の設定、書き込み手順は
[`firmware/esp32-s3-recorder/README.md`](../../firmware/esp32-s3-recorder/README.md) にあります。
通信切断・混雑・サーバー障害のときは同じアップロードIDで1件を再送するため、VRT側の重複防止と組み合わせて二重登録を避けます。無効な端末キーなど、再送しても直らないHTTP `4xx`では音声を端末から削除し、設定ミスで新しい録音が止まり続けないようにします。

起動中の開発APIへ、端末の立場で匿名化済みのテスト候補を送るには次を使います。`【端末テスト】` と明示した記録が作成され、先生の承認待ちになります。

```bash
.venv/bin/python scripts/send_demo_from_edge.py
```

その候補を管理者として承認する補助コマンドです。試用園では通知が `trial`、本番園でLINE未連携なら `waiting_guardian_link` になるため、送信待ち件数だけで合否を判断しないでください。

```bash
.venv/bin/python scripts/approve_latest_edge_demo.py
```
