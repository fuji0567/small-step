# Small Step 録音

`/rec/` で配信する、先生向けの独立録音PWAです。既存の `frontend/` とは依存関係とビルド成果物を分離しています。

## 開発

Node.js 24.19.0を使用します。

```powershell
npm install
npm run format:check
npm run lint
npm run check
npm run test:unit
npm run build
```

`npm run build` は `app/recorder_dist/` を生成します。開発サーバーは `/api/v1` を `127.0.0.1:8000` へ転送します。

録音中は画面を前面に保つ必要があります。音声は約1分ごとに独立ファイルとしてIndexedDBへ保存し、受付完了・破棄・24時間経過で端末から削除します。自動再送は利用者が送信を選んだ後に通信が途切れた録音だけを対象とします。アクセストークンと更新トークンは `sessionStorage` だけに保存し、Service WorkerはAPI応答・認証情報・音声をキャッシュしません。
