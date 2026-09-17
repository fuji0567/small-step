# VRT録音デモ導入手順

`/rec/` はESP録音端末の代わりにスマートフォンで試すデモ用入口です。
既定の連続モードは、明示的な開始後に60秒ごとに自動送信し、録音を続けながら前の区間を処理します。
停止時の端数も自動送信します。チェックを外した手動モードは停止後に送信します。
真のストリーミング認識ではなく、前面表示中だけの連続録音です。画面ロック・スリープ・強制終了中は保証しません。
実機音声による確認は別途必要です。この手順だけで実運用完了とはしません。

## 導入前の検証

2026-09-17にNode.js 24.19.0で両フロントエンドのformat、lint、型検査、単体テスト、ビルドを確認しました。
先生用画面は191件、録音PWAは100件の単体テストが成功しています。バックエンドは229件成功、1件skipです。
これはローカルの事前検証です。Ubuntuでの移行・再作成・readiness確認と、実機録音による確認は別途行います。
録音PWAの送信テストは、実時間で完了するハッシュ計算を含むため、一定回数の待機ではなく受付表示と
端末データ削除の完了を待って検証します。意図的にハッシュ計算を遅らせた場合も同じ条件を満たすことを確認します。

ビルドが失敗した場合は、その後のコンテナ再作成へ進まないでください。既存イメージから起動して
`ready` が出ても、新しいコードが反映されたことを意味しません。コード取得とビルドの成功を確認してから再作成します。

## 前提

- GitHubへpush・mainへマージした後、Ubuntuでmainを取得する。
- 現在のDBバックアップと復旧手順を確認する。`.env` の控えはGitへ追加しない。
- 公開HTTPSと先生ログインが利用でき、既存GPUワーカー・vLLMが稼働している。
- 試験音声は同意済みの成人だけで録音する。園児や個人情報を含む音声は使わない。
- 生音声はVRTへ一時送信される。「音声が園外に出ない」方式ではない。

## ビルドと移行

まず `RECORDER_ENABLED=false` のまま新しいコードを導入します。

```bash
cd /home/ubuntu/small-step
sudo docker compose -f compose.yaml -f compose.vrt.yaml config --quiet
sudo docker compose -f compose.yaml -f compose.vrt.yaml build api migrate gpu-worker
sudo docker compose -f compose.yaml -f compose.vrt.yaml run --rm --no-deps migrate
```

各処理の成功を確認してから次へ進みます。移行は `0024_recorder_worker` まで適用します。
既存テーブルの保護を維持したまま、排他処理と内容を持たない進捗カウンターを追加します。
障害時は録音無効化を優先します。APIだけ旧版へ戻すと移行番号不一致でreadinessが失敗します。

## 試験用に有効化

Ubuntuの `.env` の既存行を変更します。同じ設定を末尾に重複追加しないでください。
トークンや秘密鍵をチャットへ貼り付ける必要はありません。

```dotenv
CLOUD_AUDIO_ENABLED=true
RECORDER_ENABLED=true
RECORDER_WORKER_HEARTBEAT_REQUIRED=true
RECORDER_PROCESSING_TIMEOUT_MINUTES=10
```

APIとGPUワーカーは同じ `api_data` の `/app/data/recorder-sessions` を共有します。
既存APIが稼働している状態で、GPUワーカーを先に再作成します。
Dockerのhealthyと運用開始用readinessは別の判定です。APIがhealthyでも、録音処理の生存確認が
更新されるまではreadinessが失敗するため、最後に必ず確認してください。

```bash
sudo docker compose -f compose.yaml -f compose.vrt.yaml up -d --no-deps --force-recreate gpu-worker
```

ワーカーの起動を確認してからAPIを再作成します。

```bash
sudo docker compose -f compose.yaml -f compose.vrt.yaml up -d --no-deps --force-recreate --wait api
sudo docker compose -f compose.yaml -f compose.vrt.yaml exec -T api python scripts/check_runtime_readiness.py
```

`status: ready` と `cloud_audio_worker_ready: true` を確認します。録音有効時はこの判定に
通常音声と録音処理の両方の生存確認を含みます。モデル精度や実録音の成功までは保証しません。

## 実機での確認

1. `https://app.otayori-ai.com/rec/` で先生としてログインする。
2. 自動送信の注意を確認して「連続録音・自動送信を開始」を押し、前面に表示したまま125〜135秒録音する。
   最初と最後に異なる架空の出来事を話し、60秒・120秒で自動送信され録音が続くことを確認する。
3. 録音画面で受付数・未送信数と、直近のワーカー待ち→処理中→完了を確認する。停止時には短い最後の区間も送信される。
4. 先生用「音声処理状況」で各区間の結果と匿名化・園・担当を確認する。園児は未選択で承認待ちになる。
   区間をまたぐ文脈は統合しないため、候補の重複や抜けを確認する。処理が遅ければ次の送信は直前の処理終了まで待つ。
5. 別の一般先生には記録が見えないこと、承認前にLINE通知が作成されないことを確認する。
6. 個人情報や音声本体を表示せず、サーバーの残存ファイル数だけを確認する。

連続録音中に通信を切り、未送信が3区間になった時点で一時停止することを確認します。
通信を戻しても録音が勝手に再開せず、未送信の減少後に「録音を再開」で再開できることを確認します。
背面表示・マイク中断でも一時停止し、認証が更新できなければマイクを停止します。
1回の明示開始で最長12時間です。実際の長時間試験、端末の発熱・電源・画面維持とGPU使用量を別途確認してください。
ページを閉じたときに最後の未確定区間を保存できる保証はありません。閉じる前に停止し、未送信0を確認してください。
手動モードでは従来の65〜75秒の停止後送信と、破棄操作も回帰確認します。

```bash
sudo docker compose -f compose.yaml -f compose.vrt.yaml exec -T gpu-worker python3 -c '
from pathlib import Path
from app.config import Settings
p = Path(Settings().recorder_session_dir)
print("残存音声ファイル数:", sum(1 for f in p.rglob("*") if f.is_file()) if p.exists() else 0)
'
```

他の未処理録音がない試験環境では0になります。無発話・具体的な出来事なしは完了でも記録を作成しません。
部分失敗は警告付きの承認待ち記録になり、内容と抜け漏れを確認する必要があります。
既知のけがを含む候補の統合に失敗した場合はセッション全体を失敗にします。
現在の記録発生日時はサーバーの受付日時です。端末の録音開始時刻ではありません。

受付後に通信を一時切断し、状態確認が停止し、復旧時に再送なしで追跡が再開することも確認します。
別画面へ切り替えた場合も自動確認を中断し、前面へ戻ると再開します。待機へ戻ってもサーバーの処理は継続します。
処理失敗・期限切れは再録音や手入力を案内し、同じ音声の再送を行いません。候補なしの完了は正常な結果として案内します。

## 任意の先生声紋照合

本機能は `/rec/` の録音だけの担当候補表示です。ESPの音声ジョブ、先生ログインの認証方式、
記録の実担当・承認・LINE配信は自動変更しません。機能ブランチをmainへ反映後、新コードを取得し、
録音を一時停止して処理中セッションが完了したことを確認します。既存の暗号鍵やトークンは再生成しません。

```bash
sudo docker compose -f compose.yaml -f compose.vrt.yaml build api migrate gpu-worker
sudo docker compose -f compose.yaml -f compose.vrt.yaml run --rm --no-deps migrate
```

`.env` に以下を追加します（既存 `RECORDER_ENABLED=true` と `VOICEPRINT_ENABLED=true` が必要）。

```dotenv
RECORDER_VOICEPRINT_MATCHING_ENABLED=true
RECORDER_VOICEPRINT_MATCH_THRESHOLD=0.85
RECORDER_VOICEPRINT_MATCH_MARGIN=0.1
```

```bash
sudo docker compose -f compose.yaml -f compose.vrt.yaml up -d --no-deps --force-recreate --wait gpu-worker
sudo docker compose -f compose.yaml -f compose.vrt.yaml up -d --no-deps --force-recreate --wait api
sudo docker compose -f compose.yaml -f compose.vrt.yaml exec -T api python scripts/check_runtime_readiness.py
```

先生本人が「声紋設定」の追加同意を選んで更新します。登録済み声紋が有効であれば再登録は不要です。
先生が単独で3秒以上話す新しい録音を送り、記録が生成された場合に詳細へ担当候補が出ること、
実担当が元の録音者のままであることを確認します。一般の先生の画面に担当変更操作がないことも確認します。
同じ園で同意済みの別の先生も試し、未登録・同意対象外・別の園の声、複数先生の一致・曖昧な一致では
誤った単一候補を出さないことを検査します。短い・重なる・雑音の多い声では未特定になり得ます。
類似度は確率ではありません。初期閾値のまま本番精度が保証されるわけではなく、誤一致・見逃し、
推論時間、共有GPUの空きメモリを実音声で評価してください。
追加同意を外して更新し、同じ記録を再読み込みすると候補が消えることも確認します。
照合だけを停止する場合は `RECORDER_VOICEPRINT_MATCHING_ENABLED=false` にしてAPI・GPUワーカーを再作成します。

## 任意の園児候補

録音を停止し、処理中セッションが完了してから新しいコードを取得します。
`build api migrate gpu-worker`、`run --rm --no-deps migrate` で `0026_recorder_child_suggestions` を適用し、
`.env` の `RECORDER_CHILD_MATCHING_ENABLED=true`（`RECORDER_ENABLED=true` が必要）を設定します。
APIとGPUワーカーを `up -d --no-deps --force-recreate --wait` で再作成しreadinessを確認します。
既存の暗号鍵・トークン・声紋モデルは変更しません。本機能は先生の声紋照合に依存しません。

管理者が「園児・保護者」→「表示名を編集」で、敬称なしの呼び名・読み方を最大5件登録します。
同じ園の在籍園児を一人だけ含む架空の出来事を録音し、日誌の詳細で園児が仮選択されること、
確認チェック前は承認できず、DB上の実園児と配信先が未確定であることを確認します。
候補とは別の園児を手動選択して確定できること、園児変更でチェックが外れることも確認します。
同名（退園者を含む）、複数名、呼びかけだけ、未登録名、別の園、区間をまたぐ異なる対象で
誤った候補が出ないこと、本文に既知の名前や `園児候補_001` が残らないことを実機で確認してください。
誤変換や未登録名の匿名化、候補の見逃し・誤一致はまだ実機評価が必要で、初期実装の精度は保証しません。
実データでの試験や保護者配信は避け、まず架空データで先生が本文と園児を確認します。
無効化は `RECORDER_CHILD_MATCHING_ENABLED=false` とAPI・GPUワーカー再作成です。
無効化しても録音由来の園児確認チェックは必須です。

## 録音の失敗時と無効化

各区間の解析・統合は最大2回まで試します。中間結果はメモリにしか保持しないため、処理中の
ワーカー再起動後は途中再開しません。10分間進捗がないセッションは失敗となり、再録音が必要です。
成功・失敗・破棄・期限切れ音声の削除は定期処理と起動時に再試行します。
全ワーカー停止中は期限監視も停止するため、停止を放置しないでください。

試験を止める場合は `.env` の `RECORDER_ENABLED=false` に変更し、APIとGPUワーカーを再作成します。
無効化後もGPUワーカーの期限監視・後片付けは稼働します。録音用生存確認は必須条件から外れます。
録音PWA・録音APIは非公開になり、新しい録音の受付・処理は止まります。

```bash
sudo docker compose -f compose.yaml -f compose.vrt.yaml up -d --no-deps --force-recreate --wait api
sudo docker compose -f compose.yaml -f compose.vrt.yaml up -d --no-deps --force-recreate gpu-worker
```
# 録音処理の失敗ログ

GPUワーカーは失敗した工程 (`stage`) と許可された例外の種類 (`types`) だけを出力します。
追加診断 (`codes`) は固定の分類コードと既知のライブラリ内の行番号だけを表示します。
`invalid_numeric_values` は不正数値、`insufficient_or_invalid_shape` はデータ不足または形状不正の手がかりです。
分類はエラー文の一部を判定したもので、録音者や録音方法に原因があることを意味しません。
例外本文、音声、文字起こし、ファイルパス、セッションID、接続情報は出力しません。
`audio_analysis` は文字起こし・話者分離・要約を含みます。種類だけで原因が確定しない場合もあります。
進捗の完了区間数には失敗した区間も含まれます。失敗した音声は削除されるため、修正後の確認には新しい録音が必要です。
