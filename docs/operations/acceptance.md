# 導入時の実機・外部サービス確認

[README](../../README.md) / [デプロイ仕様](../architecture/deployment.md)

ローカルのテスト成功と、配備先での動作確認は別に記録します。この一覧は確認項目であり、
現在のVRT・LINE・端末の稼働状況を保証するものではありません。

| 対象 | 確認すること | 手順 |
| --- | --- | --- |
| 配備 | 適用したGit revision・image、DB migration、API・全ワーカーのreadiness | [初期設定](setup.md)、[VRT音声](audio.md) |
| 認証・権限 | 管理者・一般先生・別園・停止中先生で許可と拒否を確認 | [認証仕様](../architecture/auth.md)、[先生招待](../teacher-invitations.md) |
| 試用 | 承認後もLINE・アーカイブ・Notionへ出ず、本番へ戻しても試用記録が配信されない | [園別試用](../school-trial-runbook.md) |
| スマートフォン | HTTPS、マイク、60秒区間、停止時の端数、回線断・認証切れ・前面復帰 | [録音導入](../recorder-vrt-runbook.md) |
| 音声精度 | 複数話者・雑音・声量差・対象外を含むテストと人による生成文評価 | [音声評価](audio.md#実音声テストセットの精度確認) |
| ESP32-S3 | 書き込み、PSRAM、マイク配線、無音しきい値、拒否・再送 | [実機README](../../firmware/esp32-s3-recorder/README.md) |
| LINE・アーカイブ・Notion | 同意済みテスト宛先への送信と閲覧範囲、重複・失効・同期拒否 | [初期設定](setup.md)、[外部連携仕様](../architecture/integrations.md) |
| バックアップ | 非公開S3とage鍵、外部保存、復号と使い捨てDBへの復元 | [バックアップ](backup-monitoring.md) |
| 監視 | VRT内とGitHub Actionsの両方で障害・復旧を確認。固定HTTPS URLを設定 | [監視](backup-monitoring.md) |

結果には実施日、対象revision、環境、成功／失敗、未確認項目を残します。
音声、文字起こし、園児名、URLの秘密部分、鍵は検証ログへ含めません。
