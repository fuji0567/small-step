# エッジ音声・VRT・MCPの導入と検証

[README](../../README.md) / [音声処理仕様](../architecture/audio-pipeline.md)

コマンドはリポジトリのルートで実行します。`.venv313` は音声用に別途作成する仮想環境の名前です。
API用の `.venv` とは分け、使用するPython・PyTorch・CUDAの組み合わせを処理端末で確認してください。
`python3.13 -m venv .venv313` などで作成してから、以下の追加依存を入れます。
この手順の設定例は部分設定であり、本番認証・DB・HTTPSの準備も必要です。

MCP（Model Context Protocol）サーバーは、マイクに近い園内PCまたは高火力VRTのGPUワーカーで動かします。公開するFastAPIやLINE Webhookで動かすものではありません。

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
- `analyze_audio_file`: 許可したローカルフォルダ内の音声を、匿名化済み候補へ変換する。APIへは保存しない。
- `submit_analyzed_audio_file`: 匿名化済み候補を先生の承認待ち記録として登録する。LINE送信はできない。

### 安全な前提

- 音声ファイルは `EDGE_AUDIO_INBOX_DIR` 配下の `.wav`、`.mp3`、`.m4a`、`.mp4`、`.aac`、`.ogg`、`.flac`、`.webm` だけを受け付けます。
- 既定では処理の成否にかかわらず音声ファイルを削除します。生の文字起こしもDB・API応答・MCP応答へ保存しません。
- LLMの接続先は既定で `localhost` だけです。外部ホストを使うには、リスクを確認して `LLM_ALLOW_EXTERNAL=true` を明示する必要があります。
- `injury` と判定されても、必ず先生の承認を通ります。MCPやLLMだけでLINE通知されることはありません。

### 高火力 VRTでクラウド音声処理する準備

園内の高性能PCを置かず、さくらの高火力 VRTへ音声を送ってGPU処理するためのジョブ基盤を用意しています。最初の実証では、FastAPIとGPUワーカーを**同じVRT**で動かし、同じ非公開ディレクトリを共有します。録音端末は登録済みの端末キーで、`multipart/form-data` の `audio` ファイルを `POST /api/v1/edge/audio-jobs` へ送信します。

クラウド音声モードは初期状態で無効です。園・先生・保護者への説明と同意、通信経路、運用責任者を決めるまで `false` のままにしてください。

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

録音端末は、VRTのAPIが準備できた後に端末側の `.env` で次のように切り替えます。`cloud` モードでは端末内の文字起こし・LLMは起動せず、VRTが受信に成功したときだけ端末の音声ファイルを削除します。通信失敗時は端末に残るため、次回の監視で再送できます。

```dotenv
EDGE_AUDIO_PROCESSING_MODE=cloud
EDGE_API_URL=https://<VRTの非公開URLまたはHTTPS公開URL>
EDGE_API_KEY=<その録音端末専用のキー>
EDGE_DEVICE_HEARTBEAT_INTERVAL_SECONDS=60
```

VRT側では `CLOUD_AUDIO_ENABLED=true` を設定します。端末・VRTともに `.env` はGitへ追加しません。

VRTとの通信が一時的に切れた場合、端末は音声を削除せずに残します。再接続後は10秒、20秒、40秒のように待機時間を延ばしながら再送します（最大5分）。同じ音声には端末内だけで管理するランダムな送信IDを付けるため、サーバーの受信結果が通信途中で分からなくなった場合も、VRT上に同じ音声ジョブを二重に作りません。送信を受け付けた応答を確認できたときだけ端末側の音声を削除します。

30秒区切りの前後で同じ出来事が重複して候補化された場合は、同じ園児・同じ録音端末・同じ種別・2分以内・未承認で、要約がほぼ同じものだけを既存の記録へまとめます。園児未選択、承認済み、文章が異なる候補は自動統合しません。

VRT上では、FastAPIを起動した後に別プロセスでGPUワーカーを起動します。`--once` は1回だけの安全な検証用です。

```bash
.venv313/bin/python -m pip install -e '.[edge-audio,speaker-diarization]'
.venv313/bin/python scripts/process_cloud_audio_jobs.py --once
```

通常運用では `--once` を外します。待機中ジョブの取得はDBで原子的に行うため、複数のGPUワーカーを誤って起動しても同じジョブを同時に処理しません。最初のVRTではGPUメモリ管理を単純にするため、まずは1プロセスで運用してください。APIとGPUワーカーを別VMへ分ける段階では、次に暗号化したオブジェクトストレージとキューへ置き換えます。

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
[`docs/vrt-audio-evaluation-manifest.example.json`](../vrt-audio-evaluation-manifest.example.json)です。
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

### VRTへの初回配置

Macでの開発中は、これまでどおり次だけを使います。GPUワーカーは起動しないため、Mac用の設定や音声テストを変える必要はありません。

```bash
docker compose up --build
```

VRTを借りられたら、このリポジトリと `.env` をVRTへ置き、VRT上の `.env` だけで次を有効にします。`.env` はGitへ追加しません。

```dotenv
APP_ENV=production
AUTH_MODE=supabase
SUPABASE_URL=https://<プロジェクト>.supabase.co
SUPABASE_PUBLISHABLE_KEY=<公開キー>
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

次でデータベース準備・vLLM・API・GPUワーカーを一緒に起動できます。`compose.vrt.yaml` はMacでは使いません。空のDBでは`migrate`が初期構成を適用し、vLLMとAPIがHealthyになってから各ワーカーが順番に起動します。Qwenの読込中は数分待ちます。

```bash
docker compose -f compose.yaml -f compose.vrt.yaml config --quiet
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

`ready` 以外の場合は、そのVRTへ録音端末を切り替えずに `.env` と `migrate` のログを見直します。LINE配信設定は表示のみで、LINEをまだ接続していない開発・検証環境では `false` でもAPIは起動できます。

先生管理者は先生画面の「稼働準備」からも、同じ安全な確認結果を見られます。VRTをまだ使わない間は「Macでローカル処理中」と表示されます。VRTへ切り替えた後は、データベース更新、一時音声保存、文章生成AI、GPU音声処理、LINE配信設定、LINE送信処理の状態を、接続先やキーを表示せずに確認できます。

`APP_ENV=production`で起動する場合は、誤ってローカル開発設定を公開しないように、`AUTH_MODE=supabase`、Supabaseの公開設定、SQLite以外の`DATABASE_URL`が必須です。保護者用配信アーカイブを有効にする場合は、`GUARDIAN_ARCHIVE_BASE_URL`もHTTPS URLでなければ起動しません。

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

`.env` には、ローカルLLMのOpenAI互換エンドポイントと、端末専用APIキーを設定します。Sakura高火力VRTでvLLMを同じVMに置く場合は、LLMを `127.0.0.1` にだけ待ち受けさせます。

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

録音端末を用意する前に、Macを端末の代わりにできます。別の録音アプリなどで作成した対応形式の音声を `data/edge-audio-inbox` に置くと、Mac内で文字起こし・匿名化し、具体的な出来事がある場合だけ承認待ち記録として送信します。生音声や文字起こしはAPI・DBへ送信されません。

最初は、既存の音声を一度だけ処理する `--once` を使います。このエッジ監視経路では、園児は音声内容やファイル名から推測しません。園児IDを省略すると、先生が確認画面で対象園児を選べます。

```bash
.venv313/bin/python scripts/watch_edge_audio.py --once
```

特定の園児に紐付けたテストを行う場合だけ、園児作成時に取得したIDを明示します。

```bash
.venv313/bin/python scripts/watch_edge_audio.py --child-id <園児ID> --once
```

確認できたら、次でフォルダを常時監視します。録音が終わったファイルは、作成から2秒以上経過してから処理するため、書き込み途中のファイルを避けられます。停止は `Control+C` です。

```bash
.venv313/bin/python scripts/watch_edge_audio.py
```

監視間隔と待機秒数は `.env` の `EDGE_AUDIO_WATCH_POLL_SECONDS` と `EDGE_AUDIO_WATCH_MIN_AGE_SECONDS` で変更できます。既定では、処理を始めた音声は成功・失敗にかかわらず削除されます。

### Macのマイクから自動で録音するテスト

Macでは `ffmpeg` を使って、マイクの音声を30秒ごとのWAVファイルとしてローカル受信フォルダへ保存できます。録音中は隠し一時ファイルを使い、録音が完了してから監視プログラムへ渡すため、途中の音声は処理されません。

最初に、Macで使える音声入力の番号を確認します。`Audio devices` の一覧にある番号を控えてください。

```bash
.venv313/bin/python scripts/record_edge_audio.py --list-devices
```

別ターミナルで音声監視を起動した状態で、まず10秒の録音を1回だけ作成します。音声入力が一覧の `0` なら `:0` のままで大丈夫です。

```bash
.venv313/bin/python scripts/watch_edge_audio.py
.venv313/bin/python scripts/record_edge_audio.py --once --chunk-seconds 10 --audio-device :0
```

初回はmacOSからターミナルのマイク利用許可を求められます。許可後、録音・匿名化・承認待ち記録の作成が順に行われます。通常運用では `--once` を外します。録音秒数と既定の入力は `.env` の `EDGE_AUDIO_RECORD_CHUNK_SECONDS` と `EDGE_AUDIO_INPUT_DEVICE` で変更できます。

### 匿名の話者分離

話者分離は、生音声を処理端末内で `speaker_01` のような匿名の話者区間に分ける機能です。匿名話者ラベルから先生・園児の名前は判定しません。生の文字起こし・話者区間はDBへ保存せず、音声の送信有無はローカル／クラウドの処理モードに従います。

ローカルで動かす Community-1 モデルは、最初にHugging Faceで利用条件へ同意し、無料のアクセストークンを作る必要があります。トークンを `.env` の `SPEAKER_DIARIZATION_TOKEN` に保存してから、音声処理用環境へ追加パッケージを入れます。

```bash
.venv313/bin/python -m pip install -e '.[speaker-diarization]'
```

`SPEAKER_DIARIZATION_TOKEN` が設定されていると、通常のローカル処理とVRT処理でも自動的に匿名話者分離を行います。Whisperの単語時刻を匿名区間へ対応付け、匿名ラベル付きの文字起こしだけをQwenへ渡します。トークンが未設定なら話者分離だけを省略し、従来どおり文字起こしを続けます。

音声は `EDGE_AUDIO_INBOX_DIR` に置いたまま、次のコマンドで話者数と匿名区間だけを単体確認できます。音声ファイル名に個人名を入れないでください。

```bash
.venv313/bin/python scripts/diarize_edge_audio.py data/edge-audio-inbox/<音声ファイル名>.wav
```

最初の分離で話者が1人だけと判定された場合は、既定で元音声を変更しない一時的な音量差補正をかけ、静かな話者を検出できるか1回だけ再確認します。補正後に十分な長さの別話者が見つかったときだけ結果を採用し、一時音声は直後に削除されます。マイクに届かなかった発話や大きな雑音に埋もれた発話を復元する機能ではありません。無効にする場合は `.env` に `SPEAKER_DIARIZATION_LOW_VOLUME_RETRY=false` を設定してください。

声量差のある録音を試すときは、同意済みの成人2人が交互に話し、1人は少し小さめの声で話します。出力の読み方は次のとおりです。

```text
匿名の話者数: 2
音量差を補正して再確認した話者数: 2
補正後の結果を採用しています。
```

この場合は、最初の結果で見つからなかった静かな話者を補正後に検出できています。補正前後ともに話者数が `1` の場合は、静かな声がマイクに十分届いていない可能性があります。話者数を無理に増やさず、マイクを会話の中央に近づけるか、実機マイクで録音し直してください。

話者ラベルは、会話の交代をQwenが理解するためだけに使います。ラベル自体や話者区間は通知・成長記録・DBに保存しません。

録音時点で園児IDが指定されている場合は、同じ園児の直近5件の承認済み・配信済み記録も匿名の参考情報としてQwenへ渡します。現在の音声と過去記録の両方に根拠がある場合だけ、小さな変化を候補文へ含めます。園児未選択、未承認記録、別の園児の履歴は参照しません。

### 声紋の登録と本人確認

声紋機能は既定で無効です。VRT管理者が必要な設定を有効にした園では、先生が先生画面の「声紋設定」で次を自分で確認して同意します。

- 利用目的は声紋の登録・本人確認であること（録音内の先生照合は別の任意同意）
- 同意の有効期限（1〜365日）
- いつでも同意を取り消せること

同意後、先生本人がブラウザの録音ボタンで10〜15秒の音声を3回録音します。GPUワーカーは各回について録音時間、発話時間、声量、雑音、音割れ、複数話者を確認し、品質基準を満たさない場合は該当回の再録音を案内します。3回分の特徴量を平均し、暗号化した代表声紋だけを先生ごとに1件保存します。個別特徴量は平均化後すぐメモリから消去し、元音声も成功・失敗にかかわらず処理後に削除します。マイク録音に対応していない端末では3件の音声ファイルも選択できます。本人確認は10〜15秒の音声1回と保存済み代表声紋との1対1照合であり、先生のログインを置き換えるものではありません。

先生は同じ画面から再登録、本人確認、削除ができます。同意の取消または先生アカウントの利用停止時には、登録済み特徴量、処理ジョブ、残っている一時音声を削除します。通常の業務DBバックアップには声紋特徴量と照合ジョブの行を含めません。

VRTで有効にする場合は、`.env` に次を設定して `api` と `gpu-worker` を再作成します。暗号鍵はGitへ追加せず、紛失すると登録済み声紋を復号できないため、秘密情報として安全に保管してください。

```bash
VOICEPRINT_ENABLED=true
VOICEPRINT_ENCRYPTION_KEY=<Fernet形式の秘密鍵>
VOICEPRINT_MODEL=pyannote/embedding
VOICEPRINT_MATCH_THRESHOLD=0.75
```

暗号鍵は次で生成できます。声紋機能には `CLOUD_AUDIO_ENABLED=true` と `SPEAKER_DIARIZATION_TOKEN` も必要です。

```bash
python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

#### 録音からの担当候補

`/rec/` の連続録音・手動録音は、`RECORDER_VOICEPRINT_MATCHING_ENABLED=true` で登録声紋と照合できます。
`RECORDER_ENABLED=true`、`VOICEPRINT_ENABLED=true` も必要です。先生本人が「声紋設定」で
「同じ園の録音から私の声を照合し、担当候補を表示する」を選び、同意を更新してください。
既存の同意は自動的に照合へ転用しません。有効な登録声紋があれば追加同意だけで利用でき、再登録は不要です。

同じ園の有効・同意済み・同じモデルの声紋だけを照合し、話者ごとの重なっていない発話を3〜10秒、
最大8話者までメモリで扱います。短い・小さい・音割れした発話は使いません。
一致基準は `RECORDER_VOICEPRINT_MATCH_THRESHOLD=0.85`、次点との差は
`RECORDER_VOICEPRINT_MATCH_MARGIN=0.1` が初期値です。類似度は本人である確率ではなく、
本番利用前に同意した先生の実音声で誤一致・見逃しを評価して調整してください。
複数の先生に一致、曖昧な一致、照合失敗、一部音声処理失敗では「先生未特定」とします。

記録詳細に担当候補を表示しますが、録音内の話者と記録の責任者は同じとは限りません。
実際の担当はログインした先生のままです。管理者が候補を引き継ぎ先に選び、既存の「担当を変更」で
確認すると引き継ぎます。承認・LINE配信も引き続き先生の操作が必要です。
一時特徴量は処理直後に消去し、録音音声は従来どおり処理後に削除します。候補の先生IDと実施有無だけを
記録へ保持し、類似度・話者ラベル・区間・特徴量は保存しません。候補情報は通常の記録バックアップに含まれます。
照合の追加同意を外す、同意取消、声紋削除・再登録、利用停止、同意・声紋の期限後の清掃で既存候補も削除します。
表示時にも同意・期限・園を再確認します。登録声紋のないバックアップ復元先には候補を表示しません。

Ubuntuへの反映は、新コード取得、`api migrate gpu-worker` のビルド、`migrate` による
`0025_recorder_voiceprint` の適用、上記設定追加後のAPI・GPUワーカー再作成の順で行います。
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
