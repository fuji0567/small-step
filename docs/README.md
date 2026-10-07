# 文書一覧と管理方針

[利用者向けREADME](../README.md) / [共通仕様](specification.md) / [技術構成](architecture.md)

## 読む順序

| 読者・目的 | 入口 | 続いて読む文書 |
| --- | --- | --- |
| 初めて使う人 | [README](../README.md) | [先生・保護者の使い方](usage.md)、[録音](recorder-usage.md) |
| 機能の仕様を確認する人 | [共通仕様](specification.md) | [技術構成](architecture.md)から該当領域へ |
| 導入・運用する人 | [初期設定](operations/setup.md) | [音声導入](operations/audio.md)、[バックアップ・監視](operations/backup-monitoring.md) |
| 園や任意機能を有効にする人 | [園別試用](school-trial-runbook.md) | [録音導入](recorder-vrt-runbook.md)、[先生招待](teacher-invitations.md)、[処理表示](recorder-processing-demo.md) |
| 配備先を検証する人 | [実機・外部確認](operations/acceptance.md) | 対象環境の結果を日付・revisionと共に記録 |
| 画面を設計する人 | [画面遷移](transition.md) | [画面構成](architecture/frontend.md)、[デザインシステム](design-system-digital-agency.md) |
| エージェント | [CLAUDE.md](../CLAUDE.md) | この索引と対象領域の仕様。AGENTS.mdは参照のみ |

## 仕様と履歴の区別

READMEは概要・使い方・起動・技術構成への入口です。共通仕様は横断する契約、領域別仕様は処理・
状態・モジュールの詳細、手順書は実行する順番を扱います。設定キーと制約は `app/config.py`、
設定例は [.env.example](../.env.example)、APIの正確な入出力は起動中の `/docs` と実装で確認します。

同じ詳細を複数文書へコピーせず、担当文書へリンクします。短い概要が必要な場合は、該当する詳細仕様を併記します。
実装と仕様が異なる場合は根拠を確認して両者を揃え、未実装の希望を実装済みとして書きません。
現在のリポジトリ構成と配備先での確認結果は別です。過去の件数や未確認項目を現在の検証結果へ流用しません。

| 履歴・参考資料 | 扱い |
| --- | --- |
| [Svelte移行手順](svelte-migration-runbook.md) | 2026-09-12の移行計画と検証記録。現在の作業指示・全機能の復旧手順には使わない |
| [旧画面遷移](history/legacy-screen-transitions.md) | マウントされていないHTML/JS画面の履歴 |
| [開発議事録](meeting-notes/2026-08-25.md)、[VRT準備議事録](meeting-notes/2026-09-14.md) | 記載時点の判断・結果。現在の仕様は共通仕様と領域別仕様で確認 |
| [矛盾点整理](documentation-reconciliation.md) | 今回の修正根拠と残る確認範囲 |
| [DADS原文の複製](reference/dads/ABOUT-THIS-COPY.md) | 参照資料。編集せず、プロジェクトの仕様とは区別 |

READMEに以前あった初期設定・音声・バックアップ・監視のコマンドは `operations/` へ移しています。
既存の園別試用・録音・先生招待・実機READMEのパスは維持しています。
