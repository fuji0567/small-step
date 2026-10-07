# 文書の矛盾点と整理結果

2026-10-02、作業ブランチ `codex/docs-refactor` でリポジトリのMarkdown、対応する実装、
構成例を照合しました。アプリ・DB・環境設定の変更ではなく、既存の動作を文書へ反映する整理です。
配備先、LINE、Supabase、GPU、実端末の動作はこの作業で再検証していません。

## 矛盾点・欠落・読み違いが起きる記述

| 元の記述／問題 | 実装で確認した内容と整理 | 根拠 | 反映先 |
| --- | --- | --- | --- |
| 全経路で生音声をAPIへ渡さない | localは加工済みテキスト、cloud・PWA・声紋は短命音声ファイル。業務DB保存を禁止する境界と区別 | [API](../app/api/routes.py)、[音声](../app/cloud_audio.py) | 共通仕様、技術構成、音声仕様、CLAUDE |
| 園児未指定の承認がpending通知になる | 未選択は422、退園済みも拒否。PWAは明示選択と確認フラグ必須 | [approve_record](../app/api/routes.py) | 共通仕様、データモデル |
| 通常状態表にtrialがない | 試用承認は送信先なしのtrial、記録はapprovedのまま。試用切替で未配信分等も試用扱い | [状態](../app/models.py)、[試用](../app/trial.py) | 共通仕様、データモデル、CLAUDE |
| rejectedからdispatchedにも読める矢印 | pending_reviewからapprovedまたはrejected、dispatchedへ進むのはapprovedだけ | [状態と承認](../app/api/routes.py) | データモデル、CLAUDE |
| 一般先生が園内の全記録を扱えるように読める | 園に加え担当で記録と通知を制限。録音の単一取得・変更・処理表示は管理者でも本人限定 | [記録・録音API](../app/api/routes.py)、[認可](../app/api/dependencies.py) | 共通仕様、認証仕様 |
| 先生画面は外部オリジンへ通信しない | 業務APIは同一オリジン、認証・パスワード設定・PWAのtoken更新はSupabaseへ直接通信 | [先生認証](../frontend/src/lib/auth/)、[録音](../recorder_frontend/src/) | 共通仕様、画面仕様、CLAUDE |
| secret keyをAPIにも設定しない | 通常認証は公開キー。先生招待を有効にするAPIだけサーバー専用secret keyを使う | [先生招待](../app/teacher_invitations.py) | 初期設定、共通仕様 |
| 設定差替えテストは本番環境変数を読まない | Settingsの未指定項目は.envと環境変数を読む | [設定](../app/config.py) | API仕様、README |
| エンドポイントが57本／70本、監査25種類 | 追加実装で固定件数が古くなっている。分類は残し、正確な一覧はOpenAPIとenumを参照 | [routes](../app/api/routes.py)、[AuditEventAction](../app/models.py) | API・データモデル、CLAUDE |
| 主キーはすべてUUID、heartbeat表が一覧にない | heartbeatは固定名が主キー。業務UUIDと区別してテーブル一覧へ追加 | [モデル](../app/models.py) | データモデル |
| 監査保存は表示名だけ、または対象を保存とだけ説明 | DBは園・実行先生の参照と操作／対象種別等。対象IDや本文は保存せず、画面は実行者表示名を示す | [add_audit_event](../app/api/routes.py)、[モデル](../app/models.py) | 共通仕様、データモデル、CLAUDE |
| 成長／けがの既定時刻だけで明示予約を説明していない | scheduled_forを指定した場合は優先する | [approve_record](../app/api/routes.py) | 共通仕様、データモデル、README |
| 録音READMEが停止後送信のみ、逐次送信・先生候補なし | 既定の連続録音は60秒区間の自動送信。手動モードと別に説明し、任意照合は候補のみと明記 | [録音実装](../recorder_frontend/src/)、[候補](../app/recorder_voiceprint.py) | 録音README、共通仕様 |
| 許可音声拡張子の説明にmp4/aac/webmがない | SUPPORTED_AUDIO_SUFFIXESに8形式がある | [edge_audio](../app/edge_audio.py) | 音声導入手順 |
| 15分で音声が必ず物理削除されるように読める | 期限と削除実行を区別。ワーカー停止中は後片付けも停止 | [GPUワーカー](../app/cloud_audio_worker.py)、[録音ワーカー](../app/recorder_worker.py) | 共通仕様、音声仕様 |
| Dockerサービス名のLLMへ既定ガードのまま接続する説明 | 非ループバックなのでLLM_ALLOW_EXTERNAL=trueが必要。公開設定とは別 | [LLMガード](../app/edge_audio.py)、[Compose](../compose.vrt.yaml) | デプロイ仕様、共通仕様 |
| 録音導入は0024まで、試用導入はこのブランチを先にマージ | 個別機能の導入番号と現在の移行headを区別。配備revisionのheadへ揃える | [DB準備](../app/database_migrations.py)、[移行](../migrations/versions/) | 録音・試用runbook |
| 試用と他園アクセス制限が未実装に読める | 既存の園・担当・所有者の認可に従う。配備先で拒否を別途確認 | [認可](../app/api/dependencies.py)、[API](../app/api/routes.py) | 試用runbook |
| 試用ガード後でも旧Svelte移行のロールバック手順を使える | 旧移行手順は履歴。試用移行のdowngrade・旧API/worker復帰は禁止という現行制約を明記 | [試用移行](../migrations/versions/0027_school_trial_mode.py) | 文書一覧、Svelte履歴、デプロイ仕様 |
| バックアップ説明から声紋除外が読み取れない | publicの業務バックアップから声紋特徴量と声紋ジョブのデータ行を除外 | [バックアップ](../app/database_backup.py) | 共通仕様、バックアップ手順 |
| 承認確認スクリプトが新規の試用園でも送信待ちを期待 | スクリプトの期待はpendingキュー。trialやwaiting_guardian_linkでは別確認が必要 | [デモスクリプト](../scripts/create_demo_growth_record.py) | 初期設定手順の制限として明記 |
| 古いテスト件数や未完了状態が現在の検証結果に読める | 日付付き履歴と現行の確認項目を分離。配備先結果を断定しない | 移行手順、議事録、対応するテスト | 文書一覧、画面遷移、デプロイ仕様 |
| READMEに詳細運用、空見出し、将来Flutter、火曜日の切替が混在 | READMEは人間向けの概要・使い方・起動・技術構成。手順を用途別に移設 | 既存READMEと構成ファイル | README、usage、operations |
| 画面遷移文書に現行と旧HTML/JSの仕様が混在 | 現行文書に録音入口を追加、旧画面はhistoryへ分離しリンクを維持 | [配信](../app/main.py) | 画面遷移、旧画面履歴 |
| 重複防止表が途中の段落で分断 | 表を連続させ、録音クラッシュ時の制約を表の後へ移動 | 既存データモデル | データモデル |

## 整理後の文書責務

- README: 初めて使う人の入口、使い方、ローカル起動、技術構成。
- specification: 機能・権限・状態・保存境界を横断する契約の入口。
- architecture: 領域別の詳細設計と対応モジュール。
- usage / recorder-usage: 画面の操作と利用時の制約。
- operationsと既存runbook: 環境構築、有効化、検証、障害対応の順序。
- transition: 現行の画面とURLの関係。
- history・Svelte移行手順・議事録: 記載時点の履歴。現在の作業指示には使わない。
- CLAUDE: エージェントの作業規約。AGENTSは参照だけ。

設定ファイル・アプリの動作は変更していません。DADSの原文複製と議事録本文も維持しています。
開始時からの `.gitignore` と `architecture/integrations.md` の変更は保持します。

## 残る確認範囲

匿名化・候補・声紋の精度、実PostgreSQLでの競合、実LINE送信、Supabaseメール、VRT配備、
スマートフォン・ESPの実音声、外部バックアップと監視は[導入確認](operations/acceptance.md)で別途記録します。
文書整理のために本番モード切替、メール／LINE送信、移行、デプロイは実行しません。

## この作業での検証

- 対象31件のMarkdownについて、235件のローカル参照、見出しアンカー、コードフェンス、表の列数を確認しました。
- README・CLAUDE・operations中の26件のスクリプト参照と、両packageのNode指定・掲載npm scriptを確認しました。
- trial通知と試用切替の監査種別をモデル定義から確認し、変更対象がMarkdownだけであることを確認しました。
- git diff --checkは成功しました。開始時からの.gitignoreとintegrationsの差分はそのままです。
- アプリコードは変更していないため、アプリのテスト・ビルド・外部通信・実機操作は実行していません。
