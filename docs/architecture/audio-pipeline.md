# 音声パイプライン

- 索引: [../architecture.md](../architecture.md)

園内のマイクから記録候補が生まれるまでの流れです。
このパイプラインの目的は「**API に生音声と生の文字起こしを渡さないこと**」の一点に尽きます。

---

## 処理モード

`EDGE_AUDIO_PROCESSING_MODE` で 2 つのモードを切り替えます。

| モード | 文字起こしと匿名化の実行場所 | API へ送るもの | 用途 |
| --- | --- | --- | --- |
| `local`（既定） | 園内のエッジ端末 | 匿名化済みテキストのみ | 常用。音声は園から出ない |
| `cloud` | さくら高火力 VRT の GPU ワーカー | 音声（短命ジョブ）→ 処理後に削除 | エッジ端末の性能が足りないとき |

`cloud` は `CLOUD_AUDIO_ENABLED=true` も必要な、明示的なオプトインです。

---

## ローカル処理モード

```mermaid
flowchart LR
    MIC["マイク"] --> REC["record_edge_audio.py<br/>app/edge_recorder.py"]
    REC --> INBOX[("data/edge-audio-inbox")]
    INBOX --> WATCH["watch_edge_audio.py"]
    WATCH --> TRANS["faster-whisper<br/>文字起こし"]
    TRANS --> DIAR["app/speaker_diarization.py<br/>話者分離"]
    DIAR --> LLM["ローカルLLM<br/>記録対象判定・匿名化・要約"]
    LLM --> JUDGE{"具体的な出来事あり?"}
    JUDGE -->|あり| POST["POST /api/v1/edge/records"]
    JUDGE -->|なし| SKIP["記録を作らず正常完了"]
    POST --> DEL["音声ファイルを削除"]
    SKIP --> DEL
```

話者分離（`app/speaker_diarization.py`）はトークン設定時だけ処理経路へ加わり、匿名の話者ラベルと集計値だけを扱います。

| ステップ | 実装 | 補足 |
| --- | --- | --- |
| 録音 | `app/edge_recorder.py` | `EDGE_AUDIO_RECORD_CHUNK_SECONDS`（既定 30 秒）で分割 |
| 監視 | `scripts/watch_edge_audio.py` | `EDGE_AUDIO_WATCH_POLL_SECONDS` ごとに走査。書き込み途中を避けるため `EDGE_AUDIO_WATCH_MIN_AGE_SECONDS` を待つ |
| 文字起こし | `app/edge_audio.py` | faster-whisper。既定は `small` / `cpu` / `int8` |
| 話者分離 | `app/speaker_diarization.py` | トークン設定時だけpyannoteを実行。Whisperの単語時刻を`speaker_01`形式の一時ラベルへ対応付ける |
| 対象判定・匿名化 | `app/edge_audio.py` → ローカル LLM | 無音はLLMを呼ばず対象外にする。発話があっても具体的な出来事がある場合だけ候補文を生成 |
| 送信 | `POST /edge/records` | 端末 APIキーで認証。本文・種別・信頼度・発生時刻を送る |
| 後始末 | `EDGE_AUDIO_DELETE_AFTER_PROCESSING` | 既定 `true`。文字起こし・要約の成否にかかわらず、API へ送る前に音声を削除 |

### 再試行

ローカル処理モードでは再試行しません。既定では処理を始めた音声を削除するため、失敗した音声は残りません。

クラウド処理モードでアップロードに失敗した音声は、端末のインボックスに残したまま指数バックオフで再送します
（`EDGE_AUDIO_RETRY_INITIAL_SECONDS` の 10 秒から `EDGE_AUDIO_RETRY_MAX_SECONDS` の 300 秒まで）。
API が受け付けた応答を確認して初めて削除されます。

### LLM の外部送信ガード

`LLM_ALLOW_EXTERNAL` が `false`（既定）のとき、`LLM_BASE_URL` のホストは
ループバック（`127.0.0.1` / `::1` / `localhost`）に限られ、それ以外は `EdgeAudioError` で拒否されます。
文字起こし結果を誤って外部の LLM サービスへ送ってしまう事故を防ぐためのガードです。

加えて、LLM へ渡す前に `redact_obvious_identifiers()` で明らかな識別子を伏せます。
匿名化は「LLM に任せる」のではなく、送信前の伏せ字と送信後の要約の二段構えです。

---

## クラウド GPU 処理モード

```mermaid
sequenceDiagram
    participant Edge as エッジ端末
    participant API as FastAPI
    participant DB as データベース
    participant Store as 短命ジョブ保管
    participant GPU as gpu-worker（VRT）

    Edge->>API: POST /edge/audio-jobs（音声 + X-Edge-Upload-Id）
    API->>Store: ランダムキーで保存（元ファイル名は破棄）
    API->>DB: cloud_audio_jobs に queued で登録
    API-->>Edge: job_id / status=queued
    GPU->>DB: ジョブを取得（claim_token で排他）
    GPU->>Store: 音声を取得して文字起こし・匿名話者分離
    GPU->>GPU: 記録対象判定・匿名化・要約
    alt 具体的な出来事あり
        GPU->>DB: pending_review の記録を作成し completed に更新
    else 記録対象外
        GPU->>DB: record_idなしで completed に更新
    end
    GPU->>Store: 成否にかかわらず音声を削除
    Note over API,Store: 成否にかかわらず保持期限（既定 15 分）で失効
```

GPU ワーカーは API を呼ばず、API と同じデータベースとジョブ保管ディレクトリを直接使います。

| 仕組み | 実装 | 目的 |
| --- | --- | --- |
| 短命保管 | `app/cloud_audio.py` | ランダムなサーバー側キーで保存。アップロード時のファイル名は残さない |
| 排他取得 | `app/cloud_audio_worker.py` の `claim_token` | 複数ワーカーが同じジョブを処理しない |
| 重複排除 | `X-Edge-Upload-Id`（UUID） | 再送されても同じジョブを返す |
| 連続区間の統合 | `app/cloud_audio_worker.py` | 同じ園児・端末・種別で2分以内の未承認候補がほぼ同文なら、既存記録へまとめる |
| 期限切れ | `CLOUD_AUDIO_JOB_RETENTION_MINUTES`（既定 15 分） | 処理されなかった音声も必ず消える |
| 処理タイムアウト | `CLOUD_AUDIO_PROCESSING_TIMEOUT_MINUTES`（既定 10 分） | 落ちたワーカーが掴んだジョブを解放 |
| 稼働確認 | `worker_heartbeats`（既定 30 秒ごと、90 秒で停止判定） | 長時間のGPU処理中もバックグラウンドで生存を通知 |

データベースには `cloud_audio_jobs` のメタデータだけが入り、音声バイトは一切保存されません。
精度評価用に、完了時の検出話者数と音量差補正を採用したかどうかを匿名の集計値として残します。
話者ラベル、話者区間、声紋、文字起こしは保存しません。
先生用画面の「音声処理状況」ビューは `GET /audio-jobs` でこのメタデータを表示します。
`completed` かつ `record_id` がないジョブは、失敗ではなく「記録対象外」と表示します。

園児ID付きのジョブでは、同じ園児の直近5件の承認済み・配信済み記録を各500文字まで取得し、
匿名の参考情報としてローカルLLMへ渡します。現在の音声と過去記録の両方に根拠がある場合だけ、
以前との変化を候補文へ含めます。園児名・ID、未承認記録、別園児の履歴は渡しません。

AIが返した信頼度が70%未満でも候補自体は捨てません。先生画面で「要確認」として強調し、
承認時にも再確認を促します。誤配信を抑えながら、聞き取りづらい場面の見逃しを避けるためです。

---

## 話者分離

`app/speaker_diarization.py` は pyannote.audio を使い、**誰の声かを特定しません**。

- 出力は `speaker_01`, `speaker_02` のような、そのファイル内だけで有効な一時ラベルです。
- 声紋（埋め込みベクトル）は保存しません。ファイルをまたいだ同一人物の追跡もしません。
- `SPEAKER_DIARIZATION_LOW_VOLUME_RETRY`（既定 `true`）が有効なとき、
  ffmpeg で音量を均した一時 WAV を作って再試行します（元の音声は変更しません）。
  再試行の結果を採用するのは、話者が増え、かつ増えた話者に十分な発話長がある場合だけです
  （`should_use_low_volume_retry_result()`）。雑音による誤検出を採用しないための条件です。
- モデルの取得には Hugging Face のトークン（`SPEAKER_DIARIZATION_TOKEN`）が必要です。
- トークンが設定されている場合だけ通常の文字起こしへ自動統合し、未設定時は話者分離を省略します。
- Whisperの単語時刻と話者区間を突き合わせた後、LLMへ渡すのは匿名ラベル付き本文だけです。時刻と区間は保存しません。

VRTの実音声評価では、ジョブへ匿名の話者数、音量差補正の使用有無、候補の分類だけを保存します。
評価レポートは候補判定の誤検出・見逃し、分類精度、処理時間、先生による生成文の合否を集計し、
音声、文字起こし、生成文、人物名、ファイル名、ジョブID、記録IDを含めません。

単体で試すには `scripts/diarize_edge_audio.py` を使います。

### 声紋登録の同意

将来的に話者を識別する機能を入れる場合に備えて、先生ごとの同意を `voice_enrollment_consents` に記録します。
目的・ポリシー版・保持日数・同意日時・失効日時を保持し、先生用画面の「声紋設定」から
同意（`POST /voice-consent/me`）と撤回（`POST /voice-consent/me/revoke`）ができます。
同意がなくても現在の匿名話者分離は動きます。

---

## MCP サーバー

`app/mcp_server.py` は、公開 API ではなくマイクや GPU ワーカーの隣で動かすローカル専用サーバーです。
公開するツールは次の 3 つだけで、録音や LINE 送信のツールはありません。

| ツール | 内容 |
| --- | --- |
| `edge_audio_status` | 秘密情報を返さず、設定の準備状況だけを返す |
| `analyze_audio_file` | インボックス内の音声を匿名化済み候補へ変換する。API へは保存しない |
| `submit_analyzed_audio_file` | 匿名化済み候補を `POST /edge/records` で承認待ち記録として登録する |

既定は標準入出力で起動します。`--streamable-http` を指定した場合、`--host` が `localhost` またはループバック IP でなければ起動を止めます。

---

## 端末の登録と死活監視

| 操作 | エンドポイント / スクリプト |
| --- | --- |
| 端末を登録して APIキーを発行 | `POST /edge-devices` / `scripts/register_edge_device.py` |
| APIキーを再発行 | `POST /edge-devices/{id}/rotate-key` |
| 端末を無効化 | `POST /edge-devices/{id}/disable` |
| 端末側から自分の情報を確認 | `GET /edge/me` / `scripts/verify_edge_device.py` |
| 死活通知 | `POST /edge/heartbeat`（既定 60 秒間隔） |

APIキーは発行・再発行の応答でのみ平文が返り、データベースにはハッシュだけが残ります。
最終通信時刻（`last_seen_at`）は先生用画面の「録音端末」ビューに表示されます。

### ESP32-S3 実機

`firmware/esp32-s3-recorder` は、EV_INMP621-FXのPDM音声をESP32-S3内で
16 kHz・モノラル・16 bit PCMへ変換し、30秒単位のWAVとしてクラウドGPU処理モードへ送ります。
園児を音声から推測せず、通常は園児IDを空のまま送って先生のレビュー時に選択します。

録音中のPCMはPSRAMだけに置き、無音判定を通った区間だけHTTPSで送信します。
VRTが受理した場合は端末へ音声を保存しません。通信失敗時だけ1件をSPIFFSへ待避し、
保存済みの`X-Edge-Upload-Id`を変えずに再送します。待避中は新しい録音を止めるため、
古い音声を上書きしたり、停止中に端末内へ音声が増え続けたりしません。

端末は通信切断、HTTP `408`・`425`・`429`・`5xx`だけを一時障害として再送します。
認証失敗や不正な入力など、その他のHTTP `4xx`は恒久的な拒否として音声を端末から削除し、
設定不備のまま個人情報を保持し続けたり、新しい録音を永久に止めたりしません。

Wi-Fi、公開URL、端末APIキーはGit管理外の`main/secrets.h`だけに設定します。
配線・書き込み・実機確認の手順は
[`../../firmware/esp32-s3-recorder/README.md`](../../firmware/esp32-s3-recorder/README.md)を参照します。

---

## 関連する設定

キーと既定値の一覧は `.env.example` にあります（`EDGE_AUDIO_*` / `CLOUD_AUDIO_*` /
`SPEAKER_DIARIZATION_*` / `LLM_*`）。ここに写すと部分的な複製になり、片方だけ古くなるため置いていません。
このページの本文で名前を挙げているキーは、そのふるまいを説明する必要があるものだけです。
