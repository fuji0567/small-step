# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

Small Step の目的は、園で生まれた子どもの小さな成長を保護者へ届け、
家庭でも具体的に褒めてもらえる機会を増やすことです。
先生の記録負担の軽減、録音端末、文字起こし、AI による記録候補生成は、そのための手段です。
機能を設計するときは、記録件数や自動化率よりも、先生による確認、子どもの尊厳、プライバシーを優先してください。

## Git 運用

Git 運用の正本は [docs/git-rules.md](docs/git-rules.md) です。作業開始前に確認し、従ってください。
日常の開発は `develop` から `feature/` を分岐し、`main` へ直接コミットしません。
ユーザーのレビュー前には統合せず、push と `main` へのマージは対象を明示した承認が必要です。

## その他の作業指示

**Git 運用以外の詳細な作業指示は同じディレクトリの `CLAUDE.md` を参照します。始める前にそちらも読んでください。**
書いてある内容は Claude Code 向けの体裁ですが、そのまま Codex にも適用されます。

Git 運用の変更は `docs/git-rules.md`、その他の詳細な指示の変更は `CLAUDE.md` へ反映してください。
このファイルは以前 `CLAUDE.md` の全文複製でしたが、片方だけ古くなるため参照に変えました。
