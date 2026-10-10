# 録音失敗のプライバシー保護診断

## 確認できていること

2026-10-10に提供されたGPUワーカーログでは、声紋ジョブはcompleted、録音セッションは
`stage=audio_analysis; types=TypeError` で失敗しています。
この情報だけでは、文字起こし・LLM・人物候補・処理表示のどこで発生したかは特定できません。
TF32や古いチェックポイントの警告を消すだけで、この型例外を解決したとは説明しません。

## 追加する診断

`app/recorder_worker.py` の診断版は `recorder-typeerror-2026-10-10-v1` です。
従来の例外名・処理段階に加え、TypeErrorの種類を固定コードで表示します。

| コード | 意味 |
| --- | --- |
| `type_error_argument_mismatch` | 引数や関数の呼び出し方の不一致 |
| `type_error_json_serialization` | JSONへ変換できない型 |
| `type_error_container_access` | 配列・辞書などの参照方法と型の不一致 |
| `type_error_iteration` | 反復・値の展開ができない型 |
| `type_error_value_conversion` | 数値変換・演算に使えない型 |
| `type_error_unclassified` | その他、または例外文を安全に読めない場合 |

許可したモジュールだけ、固定別名とプログラムの行番号を表示します。
例えば `audio_processor` は `app.edge_audio`、`speech_transcriber` は `faster_whisper.transcribe`、
`child_matching` は `app.recorder_children`、`demo_trace` は `app.recorder_demo` です。
これはプログラム上の場所であり、音声の時刻や園児の識別番号ではありません。
例外文の全文、関数名、ファイルパス、入力、ローカル変数、音声・文字起こし・キーはログへ出しません。
分類コードも原因の確定ではなく、次に確認する処理を絞る手掛かりです。

## 反映後の確認

今回のコードは診断のみで、モデル、録音解析、声紋判定、DB、先生承認、配信、音声削除は変更しません。
ユーザー承認後にGPUワーカーだけへ反映し、録音・処理中ジョブの終了を待って切り替えます。
実行中のコードは、Ubuntuのリポジトリ直下で確認します。

```bash
sudo docker compose -f compose.yaml -f compose.vrt.yaml exec -T gpu-worker \
  python3 -c 'from app.recorder_worker import FAILURE_DIAGNOSTICS_VERSION; print("診断版:", FAILURE_DIAGNOSTICS_VERSION)'
```

反映前の録音の例外は保持していないため、新しい診断行は新たな試験から取得します。
同意した成人が架空の出来事を話す短い試験録音を、試用状態で実施してください。
実保護者へテスト配信せず、個人情報を含む台本を使いません。

```bash
sudo docker compose -f compose.yaml -f compose.vrt.yaml \
  logs --since 10m --tail 100 gpu-worker
```

`stage`、`types`、`codes` の行と診断版を確認します。生のtracebackや文字起こしを追加しません。
GPUワーカーのイメージとコード版が一致していることも確認し、行番号の示す実装を調べます。
処理済み・失敗した音声は既存の削除方針を維持します。削除済み音声の再送・再解析は約束しません。
現在はローカルの診断試験のみで、実機の原因特定・修正・再録音成功は未確認です。
