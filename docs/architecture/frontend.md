# フロントエンド

- 索引: [../architecture.md](../architecture.md)
- 画面一覧と遷移図: [../transition.md](../transition.md)
- 移行時の判断と履歴: [../svelte-migration-runbook.md](../svelte-migration-runbook.md)

現在のフロントエンドは `frontend/` の Svelte 5 runes、TypeScript、SvelteKit で構成します。
`@sveltejs/adapter-static` が `app/frontend_dist/` へ生成した静的ファイルを FastAPI が配信します。
SvelteKit のサーバーへ業務ロジックを移しておらず、API と認可の本体は引き続き FastAPI です。

| URL | SvelteKit route | 配信方式 | 対象利用者 |
| --- | --- | --- | --- |
| `/teacher/*` | `frontend/src/routes/teacher/` | CSR。`200.html` への先生用限定 SPA fallback | 先生・先生管理者 |
| `/guardian/` | `frontend/src/routes/guardian/` | prerender 済み静的ページ | 保護者 |
| `/_app/*` | SvelteKit の content hash 付き asset | `StaticFiles` | 両画面 |

`app/web/` と `app/guardian/` の旧 HTML / CSS / JavaScript は、切り替え後のロールバック用に
ファイルを保持しています。ただし現在の `/teacher/` と `/guardian/` にはマウントされません。

---

## route 構成

先生用は `frontend/src/routes/teacher/+layout.svelte` が認証、園選択、ナビゲーション、権限確認を共通で担当し、
各 `+page.svelte` は機能コンポーネントへ route parameter と共有状態を渡します。

| URL | route | 主な機能 |
| --- | --- | --- |
| `/teacher/` | `teacher/+page.svelte` | 選択園のレビュー、通知、音声処理、園児、招待の概要 |
| `/teacher/review/` | `teacher/review/+page.svelte` | レビュー待ち一覧 |
| `/teacher/review/{recordId}/` | `teacher/review/[recordId]/+page.svelte` | 日誌 1 件の取得、承認、却下 |
| `/teacher/review/new/` | `teacher/review/new/+page.svelte` | 日誌の手入力 |
| `/teacher/records/` | `teacher/records/+page.svelte` | 記録履歴、管理者の CSV 出力 |
| `/teacher/notifications/` | `teacher/notifications/+page.svelte` | 通知状況、管理者操作 |
| `/teacher/audio-jobs/` | `teacher/audio-jobs/+page.svelte` | 安全な音声処理メタデータ |
| `/teacher/children/` | `teacher/children/+page.svelte` | 園児・保護者 LINE 連携 |
| `/teacher/voice-consent/` | `teacher/voice-consent/+page.svelte` | 声紋利用への同意 |
| `/teacher/settings/` | `teacher/settings/+page.svelte` | 園設定（管理者） |
| `/teacher/teachers/` | `teacher/teachers/+page.svelte` | 先生管理（管理者） |
| `/teacher/devices/` | `teacher/devices/+page.svelte` | 録音端末（管理者） |
| `/teacher/readiness/` | `teacher/readiness/+page.svelte` | 稼働準備（管理者） |
| `/teacher/audit/` | `teacher/audit/+page.svelte` | 操作履歴（管理者） |
| `/teacher/*` の未定義 URL | `teacher/[...path]/+page.svelte` | 認証シェル内の日本語 404 |
| `/guardian/#ssa_...` | `guardian/+page.svelte` | 保護者用配信アーカイブ |

日誌の詳細 URL には不透明な `recordId` だけを含めます。`GET /api/v1/records/{record_id}` で単体取得するため、
一覧取得の上限に依存せず、直接表示、再読み込み、Back、Forward で同じ日誌を復元できます。

---

## 実装の分割

```text
frontend/src/
  lib/
    api/                 # 同一オリジンAPI client、型、安全なエラー
    auth/                # sessionStorage とtokenの初期化
    components/          # AppShell、Button、Notice、Dialogなど
    design/              # DADSに基づくCSS token
    state/               # SchoolContext、AppController、無効化scope
    features/            # dashboard、records、children等の機能単位
  routes/
    teacher/             # 先生用CSR routes
    guardian/            # 保護者用prerender route
  testsは対象実装の近くに *.test.ts として配置
frontend/tests/e2e/      # Playwrightの横断シナリオ
```

画面固有の API 呼び出し、型、表示、テストは `lib/features/<feature>/` にまとめます。
route は薄く保ち、巨大な global store や DOM の手組み、`{@html}` は使いません。

---

## API と状態管理

`lib/api/ApiClient` は同一オリジンの `/api/v1` だけを受け付けます。

- token があるときだけ `Authorization: Bearer` を付けます。
- JSON、text、Blob、204 を型ごとに処理します。
- caller の cancel と 15 秒 timeout を区別します。
- 想定外のレスポンス本文や秘密情報をそのままエラー表示しません。
- 先生用画面から外部 CDN、外部フォント、テレメトリへ通信しません。

選択園は `SchoolContext` が持ち、園を切り替えると画面固有の選択・編集中状態を消して再取得します。
更新後の横断的な再取得は `AppController` と `InvalidationScope` で接続します。
コンポーネントは mount 中だけ更新 handler を登録し、離脱時に解除します。

### ナビゲーションバッジ

`lib/features/teacher-shell/` の `NavigationBadgeService` と `NavigationBadgeState` が、認証完了後に
`GET /api/v1/navigation-badges?school_id=...` を読み込みます。選択園の変更、route の移動、対象データを
更新する `InvalidationScope` の発火後に再取得し、同じ園への同時リクエストは共有します。

取得値は必須 5 フィールドすべてが 0 以上の整数であることを確認してから使います。通信失敗や不正な応答は
補助表示だけの失敗として空の集計へ戻し、認証済みの画面やナビゲーション自体は止めません。
共通の nav item を使うため、デスクトップのサイドパネルとモバイルナビには同じ件数が表示されます。
0 件は DOM に出さず、100 件以上は視覚上 `99+` としながら、支援技術向けの `aria-label` には正確な件数を残します。
要確認・失敗の項目は `!` と warning tone を併用し、色だけに意味を持たせません。

バッジと画面の対応は [画面遷移図](../transition.md#サイドパネルとモバイルナビの通知数)、
サーバー側の集計条件と権限範囲は [API 設計](api.md#ナビゲーションバッジ集計)を参照してください。

### 補足ガイド

`Button` の `guide` と、左ナビの nav item の `guide` は、操作の補足説明を `role="tooltip"` の要素として描画し、
`aria-describedby` で対象のボタンまたはリンクに関連付けます。キーボードフォーカス時は即時、ポインターのホバー時は
600ms 後に表示し、`Escape` で閉じます（フォーカスまたはポインターが外れると再び表示できます）。

Svelte 5 の実装は runes（`$state`、`$derived`、`$effect`、`$props`）を使います。
effect の依存は入力となる状態だけに限定し、非同期読み込みで更新する内部状態を意図せず追跡しないようにします。

---

## 認証と認可

先生用の起動フローは `teacher/+layout.svelte` と `lib/features/teacher-shell/` が担当します。

1. `GET /api/v1/auth/config` で development / Supabase を判定する。
2. Supabase モードではメール・パスワードで Supabase へ直接ログインする。
3. access token を `sessionStorage` の `small-step.access-token` にだけ保存する。
4. `GET /api/v1/auth/me`、必要なら先生の紐付けまたは初回管理者設定を行う。
5. 認証後に要求された route を表示する。

一般の先生には管理者専用ナビゲーションと操作を DOM へ出しません。管理者専用 URL を直接開いた場合は
ホームへ移動して案内します。ただし UI の非表示や redirect は補助であり、認可は各 FastAPI handler の
`assert_school_access` / `assert_school_admin` / `assert_record_access` が必ず行います。

保護者用はログイン画面を持ちません。`#ssa_...` を `sessionStorage` の
`small-step.guardian-archive-token` へ保存し、SvelteKit の `$app/navigation.replaceState` で hash を消してから
`GET /api/v1/guardian/archive` を呼びます。router 初期化後に実行し、hash は SvelteKit のルーティングには使いません。
無効な token は保存領域からも破棄し、ページは `no-referrer` を指定します。

---

## 配信

`npm run build` は `app/frontend_dist/` に次を生成します。

- `200.html`: 先生用 CSR の起動ページ
- `guardian/index.html`: 保護者用 prerender ページ
- `_app/immutable/*`: content hash 付き JavaScript / CSS

FastAPI は生成物が揃っている場合だけ Svelte UI を有効にします。配信順は API、`/_app/*`、`/guardian/`、
`/teacher/*` の順です。`/teacher` は `/teacher/` へ redirect し、深い先生用 URL と未定義の先生用 URL だけを
`200.html` へ渡します。欠損 asset、API、`/guardian/` 配下の不明な URL は fallback せず 404 にします。

HTML は `Cache-Control: no-cache`、`/_app/immutable/*` は
`Cache-Control: public, max-age=31536000, immutable` です。

Dockerfile は Node.js 24.19.0 の build stage で `npm ci` と検証・ビルドを実行し、Python runtime stage には
`app/frontend_dist/` だけをコピーします。実運用環境へのデプロイ確認は別途必要です。

---

## 開発とテスト

Node.js 24.19.0 を使用します。FastAPI をポート 8000 で起動し、別ターミナルで次を実行します。
Vite 開発サーバーは `/api/v1` を FastAPI へ proxy します。

```bash
cd frontend
npm ci
npm run dev
```

検証コマンド:

```bash
npm run format:check
npm run lint
npm run check
npm run test:unit
npm run test:e2e:install  # 初回だけ
npm run test:e2e
npm run build
```

2026-09-12 の切り替え確認では、Vitest 149 件、Playwright 7 件、format、lint、Svelte check、build が成功しました。
Playwright は API をブラウザで intercept し、次を検査します。

- ホームから各 route への URL 遷移
- `/teacher/review/{recordId}/` の直接表示、reload、Back、Forward
- 先生用の日本語 404
- 保護者 token の hash 除去、再読み込み、無効化
- keyboard、focus、mobile reflow、重大・致命的な axe 違反

FastAPI の配信契約は `tests/test_frontend_delivery.py` で、先生用限定 fallback、guardian の静的配信、
欠損 asset の 404、cache header、外部オリジン参照がないことを検査します。
