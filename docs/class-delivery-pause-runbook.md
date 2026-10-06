# クラス配信の一時休止と再開

## 目的と保持するもの

約1か月、新しいクラス便・公平な個人成長便を休止し、従来の記録承認・個人配信で運用します。
`CLASS_DELIVERY_ENABLED=false` を使い、コードとDB `0029_class_digest_delivery` を維持します。
旧アプリのイメージへ戻す操作やDB downgradeは不要です。日付による自動再開は行いません。

- クラス、所属、クラス別の有効設定、人数上限、記録、送信済み履歴を保持します。
- 「今日の配信」のナビを隠し、直接URLはホームへ戻します。クラス関連APIは404です。
- 休止後の承認は従来の通知を作成します。けが経路と試用配信禁止は継続します。
- 新方式の未来の予約・送信失敗分は取り消します。通常の通知を一括取消しません。
- 新方式で承認済みだが未選定の記録は、休止しても通常通知へ自動変換しません。必要な記録は管理者が別途確認します。
- 新方式の取消済み予約は再開後も復活しません。再開日は当日の候補から先生が選びます。
- 公平回数は新方式の過去のLINE受付履歴を継続し、休止中の従来通知は加算しません。

## 初回に休止対応版を反映

レビュー済みの休止対応コードを `feature/class-delivery-pause` へpushした後の手順です。通常の `ubuntu` ユーザーで操作します。
既存の `.env` は維持し、追跡ファイルに未コミット変更があれば取得前に確認します。

```bash
cd /home/ubuntu/small-step
git status -sb
git log -1 --oneline
```

直近の検証済みDBバックアップと外部保存を確認します。新しいものがなければ次を順に実行します。

```bash
sudo docker compose -f compose.yaml -f compose.vrt.yaml --profile operations \
  run --rm --no-deps database-tools python scripts/create_database_backup.py
```

```bash
sudo docker compose -f compose.yaml -f compose.vrt.yaml --profile operations \
  run --rm --no-deps database-tools python scripts/upload_latest_database_backup.py
```

成功した場合だけ、休止対応ブランチを取得して、案内されたコミットと一致することを確認します。

```bash
git fetch https://github.com/fuji0567/small-step.git feature/class-delivery-pause
git show -s --oneline FETCH_HEAD
git switch --detach FETCH_HEAD
```

既存 `.env` に次を設定します。重複した行を作らず、ほかの設定・試用状態は変更しません。

```dotenv
CLASS_DELIVERY_ENABLED=false
```

設定確認とビルドを順に実行します。この変更は追加migrationを必要としません。

```bash
sudo docker compose -f compose.yaml -f compose.vrt.yaml config --quiet
sudo docker compose -f compose.yaml -f compose.vrt.yaml build api line-worker
```

ビルド成功後、旧ワーカーを停止してからAPIを切り替えます。停止完了前に旧ワーカーが送信を開始した通知は取消せません。

```bash
sudo docker compose -f compose.yaml -f compose.vrt.yaml stop line-worker
sudo docker compose -f compose.yaml -f compose.vrt.yaml \
  up -d --no-deps --force-recreate --wait api
```

API起動時に新方式の未送信予約を取り消します。APIがHealthyになり、全体設定がfalseであることを確認します。

```bash
sudo docker compose -f compose.yaml -f compose.vrt.yaml exec -T api \
  python -c 'from app.config import Settings; print("クラス配信:", Settings().class_delivery_enabled)'
```

新版ワーカーを同じ設定で再作成します。従来の送信待ちは、この再開後に通常どおり処理されます。

```bash
sudo docker compose -f compose.yaml -f compose.vrt.yaml \
  up -d --no-deps --force-recreate line-worker
sudo docker compose -f compose.yaml -f compose.vrt.yaml exec -T line-worker \
  python -c 'from app.config import Settings; print("クラス配信:", Settings().class_delivery_enabled)'
sudo docker compose -f compose.yaml -f compose.vrt.yaml exec -T api \
  python scripts/check_runtime_readiness.py
```

APIとワーカーでfalseを確認し、heartbeatが更新されてreadinessがreadyになったことを確認します。
GPUワーカーの再ビルド・再作成は不要です。API切替に失敗した場合はワーカーを起動せず診断します。
先生画面を再読み込みし、「今日の配信」がなく、レビュー待ち・記録履歴・通知状況が使えることを確認します。
確認テストは試用園で行い、実保護者へテスト通知を送りません。

## 約1か月後に再開

同じ対応版のまま再開するなら再ビルドやDB移行は不要です。クラス別設定も再登録しません。
先にワーカーを停止し、`.env` の同じ行をtrueへ変更します。

```bash
cd /home/ubuntu/small-step
sudo docker compose -f compose.yaml -f compose.vrt.yaml stop line-worker
```

```dotenv
CLASS_DELIVERY_ENABLED=true
```

API、ワーカーの順に同じ設定で再作成します。

```bash
sudo docker compose -f compose.yaml -f compose.vrt.yaml \
  up -d --no-deps --force-recreate --wait api
sudo docker compose -f compose.yaml -f compose.vrt.yaml \
  up -d --no-deps --force-recreate line-worker
```

初回と同じ設定確認コマンドで両方true、readinessがreadyになったことを確認します。
API起動時に切替時刻を更新し、休止中に承認した通常通知を誤取消しないようにします。
先生画面を再読み込みし、`https://app.otayori-ai.com/teacher/daily-delivery/` を開きます。
以前有効だったクラスで当日の候補を先生が確認します。以前無効だったクラスは引き続き無効です。
送信済み履歴と所属は残り、取消済み予約は自動配信されません。

## 検証範囲

ローカルではLINEをモックにし、既定休止・全APIの拒否、休止後の従来承認、未来/失敗予約の取消、
設定・所属・受付履歴の保持、通常通知の再開後送信、試用/けが経路を確認します。
PostgreSQLの実ロック競合、Ubuntuでの再作成、実LINE配信は別途確認します。
