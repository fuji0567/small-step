# バックアップ・復元確認・障害監視

[README](../../README.md) / [デプロイ仕様](../architecture/deployment.md)

以下はUbuntu/VRT上で管理者が実施する手順です。実行ディレクトリはリポジトリのルートです。

## Supabase PostgreSQLのバックアップと復元確認

Supabaseのバックアップ提供範囲は契約プランと時点によって異なります。導入・見直し時の条件は
[SupabaseのDatabase Backups](https://supabase.com/docs/guides/platform/backups)を確認してください。

このリポジトリのバックアップは、Small Stepが使う`public`スキーマをPostgreSQLのカスタム形式で
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

このアーカイブに音声ファイル、声紋特徴量と声紋ジョブのデータ行、Supabase Authのユーザー、Supabase Storageのオブジェクトは含まれません。
それらを含むプロジェクト全体の復旧はSupabase側のバックアップ方針と合わせて管理してください。また、
VRT内に1部あるだけではVRT障害への備えにならないため、作成後は暗号化された外部保管先へ複製します。
復元リハーサルに成功したファイルだけを正式な世代として扱い、世代削除は外部保管を確認してから行います。

### 暗号化した外部バックアップ

VRTの故障や誤削除に備え、検証済みバックアップを`age`公開鍵で暗号化し、AWS S3またはS3互換の非公開
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

VRTの`.env`へ次を設定します。AWS S3では`DATABASE_BACKUP_S3_ENDPOINT_URL`を空にします。S3互換サービスでは
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

Supabase AuthユーザーとSupabase Storageは、この`public`スキーマのバックアップ対象外です。現在Small Stepの
音声はVRT内の短期保存で、Supabase Storageは使用していません。Authを含むプロジェクト全体の障害には、
Supabase公式のDatabase Backupsとプロジェクト復旧手順を併用します。`auth`や`storage`スキーマをこの
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
VRT内で動く都合上、VRT全体の停止やインターネット回線断はLINEへ送れません。その範囲は次のGitHub Actions
外部監視で補います。Quick Tunnelでも利用できますが、URLが変わるたびにGitHub Secretの更新が必要です。

## VRT全体の停止を外部から検知する

`.github/workflows/external-vrt-monitor.yml`は、GitHub Actionsから5分ごとに公開中の
`/api/v1/health`を3回確認します。APIとデータベースへ接続できない状態では専用のGitHub Issueを1件だけ作成し、
復旧時にコメントを追加して閉じます。LINE用Secretも設定した場合は、最初の障害と復旧だけを運用責任者へ通知します。
同じ障害を確認し続けてもIssueを増やさず、LINEには同じ再試行キーを使います。

GitHubのリポジトリで `Settings` → `Secrets and variables` → `Actions` を開き、次を登録します。

| 種類 | 名前 | 設定する値 |
| --- | --- | --- |
| Variable | `SMALL_STEP_EXTERNAL_MONITOR_ENABLED` | 準備完了後に `true` |
| Secret | `SMALL_STEP_EXTERNAL_HEALTH_URL` | `https://公開URL/api/v1/health` |
| Secret | `LINE_CHANNEL_ACCESS_TOKEN` | VRT内部監視と同じLINEチャネルアクセストークン |
| Secret | `OPERATIONS_ALERT_LINE_USER_ID` | 通知を受ける運用責任者のLINEユーザーID |

LINE用の2つのSecretを省略した場合もGitHub Issueによる障害記録は動きます。片方だけを設定してはいけません。
Quick Tunnelを使っている間は再起動のたびにURLが変わるため、`SMALL_STEP_EXTERNAL_HEALTH_URL`も直ちに更新します。
固定URLへ切り替えた後は、このSecretの変更だけで監視を継続できます。

有効化前に `Actions` → `Small Step external VRT monitor` → `Run workflow` で手動実行します。
正常時に `外部監視: 正常` と表示されたらVariableを `true` にします。監視先URL、LINEの秘密値、園児、音声は
Issueや実行ログへ出力しません。GitHub Actionsの定期実行は数分遅れる場合があるため、これは即時フェイルオーバーではなく
VRT全体の停止を知らせる補助監視です。GPU・LINEワーカー・バックアップの詳細はVRT内の`operations-monitor`が確認します。
