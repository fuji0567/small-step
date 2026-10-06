# 園別試用モード

## できること

- 新しい園は試用で開始し、録音、AI候補作成、園児の確認、承認まで試せます。
- 試用の承認は「試用承認済み（配信なし）」です。保護者LINE送信、配信アーカイブ掲載、Notion同期はしません。
- 既存の園は本番設定を維持します。画面の「園の設定」で園ごとに切り替えます。環境変数は追加しません。
- 本番へ切り替えるには、その園の先生管理者のチェックと確認が必要です。新しい本番記録だけが配信対象になります。
- 試用に切り替えると未承認記録、処理中の録音、送信待ち・連携待ち・失敗通知も試用になります。
  本番に戻してもこれらは配信できません。取り消せない変更なので事前に管理者が確認します。
- PostgreSQLでは園の行ロックを送信中も保持します。切り替えは送信開始済みのLINE完了を待ちます。
  すでに送ったLINEは取り消せません。切り替え成功後の新しい送信を止める契約です。

## Ubuntuへの導入

配備するrevisionのレビューと必要な統合を済ませ、適用するDB移行を確認します。
試用機能の導入は `0027_school_trial_mode` を必要としますが、移行は配備revisionのheadまで適用します。
実際の反映は管理者が実施してください。ローカル検証はUbuntuでの反映を意味しません。

1. 関係者へ停止時間を案内し、ブラウザー・ESPなどの録音を停止します。処理中の音声の完了を確認します。
2. 検証済みDBバックアップと暗号化した外部退避を確認します。秘密鍵・音声・バックアップをGitへ追加しません。
3. mainを取得し、API・migrate・GPU・LINEワーカーをビルドします。まだ旧コンテナは更新しません。

```bash
cd /home/ubuntu/small-step
sudo docker compose -f compose.yaml -f compose.vrt.yaml build api migrate gpu-worker line-worker
```

4. 全ての旧API・音声処理・LINE送信プロセスを停止してから移行します。別途動かしている送信スクリプトも停止します。
   音声期限を超える長時間停止は避けてください。

```bash
sudo docker compose -f compose.yaml -f compose.vrt.yaml stop api gpu-worker line-worker
sudo docker compose -f compose.yaml -f compose.vrt.yaml run --rm --no-deps migrate
```

5. 更新済みのAPIとワーカーだけを起動します。旧イメージのまま再起動しないでください。

```bash
sudo docker compose -f compose.yaml -f compose.vrt.yaml up -d --no-deps --force-recreate --wait api
sudo docker compose -f compose.yaml -f compose.vrt.yaml up -d --no-deps --force-recreate --wait gpu-worker line-worker
sudo docker compose -f compose.yaml -f compose.vrt.yaml exec -T api python scripts/check_runtime_readiness.py
```

6. readyを確認したら、新しいテスト園で試用表示、録音候補、承認、配信なしの通知を確認します。
   実在園児ではなくテストデータを使い、実際の保護者への送信が0件であることを確認します。
7. 試用から本番に切り替えても以前の試用記録が送られないことを確認します。
   本番配信テストは同意した管理者のテストLINE宛てだけで実施してください。

## 制限と公開前の確認

- 試用モードは匿名化や録音同意の代わりにはなりません。音声の短命保管・削除方針は従来通りです。
- 運用責任者への障害LINE通知は別系統で、試用モードでも停止しません。
- 端末内に残った未送信音声はサーバー受付時の園設定を使います。本番切り替え前に未送信分を送信・破棄してください。
- 試用フラグや通知状態を直接SQLで解除しないでください。downgrade、旧コードへの復帰も誤送信につながるため禁止です。
  障害時はAPI・ワーカーを停止し、試用ガードを残した前方修正を行います。
- SQLiteの行ロックはPostgreSQLと同等ではありません。複数ワーカーでの本番運用はPostgreSQLを使います。
- ローカルでは状態・API・送信モック・移行SQL・画面を検証します。実PostgreSQLの同時切り替え、
  実LINE送信、Ubuntuでの導入は別途検証が必要です。
- 園スコープ・記録担当・録音所有者の制約は既存の[認証仕様](architecture/auth.md)に従います。
  試用設定の切り替えでも権限は広がりません。配備先で別園から拒否されることを確認します。
