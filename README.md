# お便りAI Backend

幼稚園で収集した会話から、**成長記録**と**怪我記録**の候補を管理し、先生の承認後にLINE配信へ渡すFastAPIバックエンドです。

## いま実装した範囲

- 園・先生・園児の登録
- 園内エッジAIが生成した、匿名化済み記録候補の受信
- 先生による記録候補の承認・却下・園児／文面の補正
- 成長記録は毎日17:00（Asia/Tokyo）、怪我記録は即時に配信予約
- LINE送信ワーカー用の配信待ち取得・送信済み記録
- 重複するエッジイベントの拒否
- Supabase Authの先生ログインと園単位の認可

生音声・生の文字起こしはこのAPIに送らない設計です。園内エッジで話者識別・文字起こし・匿名化を済ませ、`POST /api/v1/records` には要約などの加工済みデータだけを送ります。

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

テスト:

```bash
pytest
```

## Supabase Authを有効にする

FlutterアプリがSupabaseへ直接メール・パスワードでログインし、取得したアクセストークンをこのAPIへ `Authorization: Bearer <access_token>` として送ります。API側はSupabase Authの `/auth/v1/user` でトークンを検証するため、JWTの署名方式を個別に設定する必要はありません。

### Supabase Dashboardでの設定

1. Freeプロジェクトを作成する。
2. `Authentication > Providers > Email` でメール認証と `Confirm Email` を有効にする。
3. `Authentication > General Configuration` で `Allow new users to sign up` を無効にする。これにより、招待済みの先生だけがログインできる。
4. `Project Settings > API Keys` からProject URLと**Publishable key**を取得する。`service_role` / secret keyはFlutterにもこのAPIにも設定しない。
5. 最初の管理者ユーザーを `Authentication > Users > Add user > Send invitation` から招待する。

### APIの設定

`.env` を次のように設定して再起動します。`SUPABASE_BOOTSTRAP_ADMIN_EMAILS` は最初の園を一度だけ作るためのメールアドレスです。

```dotenv
AUTH_MODE=supabase
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
SUPABASE_BOOTSTRAP_ADMIN_EMAILS=admin@example.com
```

管理者がログインした後、そのアクセストークンで `POST /api/v1/schools` を実行すると、園と管理者先生アカウントが同時に作成されます。完了したら `SUPABASE_BOOTSTRAP_ADMIN_EMAILS` を空にして再起動してください。

最初の園と管理者を作るだけなら、次の補助スクリプトが使えます。メールアドレス・パスワードは画面に表示されません。

```bash
.venv/bin/python scripts/bootstrap_admin.py
```

作成後は `.env` の `SUPABASE_BOOTSTRAP_ADMIN_EMAILS` を空にして保存してください。

以後の先生追加は次の順です。

1. 管理者トークンで `POST /api/v1/teachers` を実行し、先生のメールアドレスを事前登録する。
2. Supabase Dashboardからそのメールアドレスへ招待を送る。
3. 先生がパスワード設定後にログインし、`POST /api/v1/auth/link-teacher` を一度呼ぶ。
4. 以後は同じアクセストークンで、自分の園のデータだけへアクセスできる。

`GET /api/v1/auth/me` で、現在のSupabaseユーザーと紐付いた先生プロフィールを取得できます。

### Flutter側のログイン例

Flutterには `supabase_flutter` を追加し、ログイン成功後の `session.accessToken` をFastAPIへのリクエストに付与します。

```dart
final response = await Supabase.instance.client.auth.signInWithPassword(
  email: email,
  password: password,
);
final token = response.session!.accessToken;
// FastAPIへ: Authorization: Bearer $token
```

## Dockerで起動

Docker Composeでは、デフォルトで永続ボリューム上のSQLiteを使います。早い試作に使えます。

```bash
cp .env.example .env
docker compose up --build
```

本番では `DATABASE_URL` をSupabase PostgreSQLなどの永続DBに設定します。また、上記のSupabase Auth設定を有効にしてください。

### Supabase PostgreSQL へ接続する

FreeプランでローカルPCやIPv4のサーバーから接続するときは、Supabase Dashboard の **Connect → Direct → Session pooler** を選びます。表示された URI はチャットに貼り付けず、ローカルで次を実行してください。

```bash
.venv/bin/python -m pip install "psycopg[binary]>=3.2.0"
.venv/bin/python scripts/configure_supabase_database.py
.venv/bin/python scripts/migrate_sqlite_to_supabase.py
```

スクリプトの最初の入力には、ダッシュボードにある `[YOUR-PASSWORD]` を含む接続文字列を貼り付けます。次の2回の入力には、プロジェクト作成時に決めた**データベース用パスワード**を入力します（Supabaseへのログイン用パスワードとは別です）。パスワードは画面に表示されず、`.env` 以外には保存されません。

最後の移行スクリプトは、ローカルSQLiteに作成済みの園・管理者・記録をSupabaseへ一度だけコピーします。Supabase側にデータがある場合は安全のため中止し、上書きしません。

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

端末からは `X-Edge-Api-Key` ヘッダーで `POST /api/v1/edge/records` を呼びます。このAPIは園・担当先生をキーから判断し、`raw_audio` のような未定義項目を受け付けません。

キーの有効性だけを確認するときは、データを書き込まない次のコマンドを使います。

```bash
.venv/bin/python scripts/verify_edge_device.py
```

起動中の開発APIへ、端末の立場で匿名化済みのテスト候補を送るには次を使います。`【端末テスト】` と明示した記録が作成され、先生の承認待ちになります。

```bash
.venv/bin/python scripts/send_demo_from_edge.py
```

その候補を管理者として承認し、通知待ちを確認するには次を実行します。

```bash
.venv/bin/python scripts/approve_latest_edge_demo.py
```

## さくらの高火力 VRTへの載せ方

高火力 VRTはGPU搭載のVMです。API自体はGPUを使わないため、このコンテナをそのまま動かし、後で同じVM上または園内エッジ側にGPU使用の `inference-worker`（Whisper・話者識別・ローカルLLM）を追加する構成にします。

1. VMにDocker EngineとDocker Composeを導入する。
2. このリポジトリをVMへ配置し、`.env` に本番の `DATABASE_URL` とSupabase Auth設定を入れる。
3. `docker compose up -d --build` でAPIを起動する。
4. リバースプロキシ（CaddyまたはNginx）でTLS終端し、APIの8000番ポートをインターネットへ直接公開しない。
5. GPUワーカーを追加する際は、モデル・一時音声は永続ディスクまたは園内側に置く。高火力 VRTの一時領域はVM停止・障害時に消えるため、そこを永続データの保存先にしない。

## 次に実装するもの

1. LINE Messaging APIの実送信ワーカーとWebhook検証
2. 高火力／園内エッジの推論ワーカー（Whisper、話者識別、分類）
3. Alembicマイグレーション、監査ログ、暗号化・保護者同意の管理
