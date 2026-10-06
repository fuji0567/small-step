# フロントエンド

- 索引: [../architecture.md](../architecture.md)
- 画面一覧と遷移図: [../transition.md](../transition.md)
- 移行時の判断と履歴: [../svelte-migration-runbook.md](../svelte-migration-runbook.md)

先生用・保護者用フロントエンドは `frontend/` の Svelte 5 runes、TypeScript、SvelteKit で構成します。
`@sveltejs/adapter-static` が `app/frontend_dist/` へ生成した静的ファイルを FastAPI が配信します。
SvelteKit のサーバーへ業務ロジックを移しておらず、API と認可の本体は引き続き FastAPI です。

園の `trial_mode` を共通レイアウトで「試用中（保護者への配信なし）」と表示します。
園の設定は先生管理者だけが利用モードを変更でき、本番への切り替えはチェックと確認ダイアログの二段階です。
記録の `is_trial` は一覧・詳細・承認確認で配信なしと明示し、通知状態 `trial` は専用表示とフィルターだけを
提供します。再送・取消・日時変更の操作は出しません。録音PWAはログイン情報の `trial_mode` を表示します。
表示は安全性の唯一の根拠ではなく、APIとLINEワーカーのDBガードが配信を防ぎます。

| URL | SvelteKit route | 配信方式 | 対象利用者 |
| --- | --- | --- | --- |
| `/teacher/*` | `frontend/src/routes/teacher/` | CSR。`200.html` への先生用限定 SPA fallback | 先生・先生管理者 |
| `/guardian/` | `frontend/src/routes/guardian/` | prerender 済み静的ページ | 保護者 |
| `/_app/*` | SvelteKit の content hash 付き asset | `StaticFiles` | 両画面 |
| `/rec/` | `recorder_frontend/` | 独立したSvelte 5＋Vite PWA | 先生・先生管理者 |
| `/rec/assets/*` | Viteのcontent hash付きasset | `StaticFiles` | 録音PWA |

`app/web/` と `app/guardian/` の旧 HTML / CSS / JavaScript は、切り替え後のロールバック用に
ファイルを保持しています。ただし現在の `/teacher/` と `/guardian/` にはマウントされません。

## 独立録音PWA

試用中にプロコン用の処理表示を有効にした場合だけ、待機画面で録音前の明示同意を取得します。
同意フラグは各ローカル録音区間のメタデータに固定し、送信時のセッション作成へ渡します。
`RecorderDemoView.svelte` は直近の受付セッションの本人用APIを、表示ボタンを押した後だけ取得します。
文字起こし・LLM指示／入力／応答・形式検証・アプリの候補／照合／最終判定を順に表示し、
期限切れ、非表示化、離脱、権限・認証エラーでは内容を消します。遅い応答は取消世代とAbortSignalで無視します。
デモ内容をブラウザ保存やService Workerキャッシュへ入れません。詳細は [実演手順](../recorder-processing-demo.md)。

`recorder_frontend/` は既存SvelteKitアプリとpackage、lockfile、ビルド成果物を共有しません。録音開始前に
サーバー接続と先生ログインを確認し、MediaRecorderを約1分ごとに停止・再作成して単独送信できるMP4/AACまたは
WebM/Opusを作ります。一時停止、停止、画面の非表示、マイク中断でも現在の端数を確定し、画面やマイクが中断した後は
利用者が明示的に再開します。実録音時間だけを数え、手動モードは60分、既定の連続モードは12時間で自動停止します。

連続モードは、周囲への通知と明示的な開始操作を前提に、確定した60秒区間を別のクライアントUUID、連番0の
`uploading` セッションとして保存し、自動送信します。停止・一時停止時の端数も同様です。
端末保存だけを待って次の区間を開始し、ネットワークや推論の完了は待ちません。
`ContinuousUploadQueue` は送信を直列化し、同じ稼働中のキューでは直前に受け付けたジョブが終端になるまで
次を送信しません。約10秒ごとに再試行し、録音中に受付数・未送信数・直近の処理状態を表示します。
端末に3件残った時点で録音を一時停止し、送信が復旧しても録音は自動再開しません。
キューの受付ID追跡はメモリのみで、ページ再読み込みをまたぐサーバー全体のジョブ数制限ではありません。
受付済み区間は送信直後に端末から削除し、再送には同じUUIDとハッシュを使います。同じアップローダーの
重複呼び出しは同じPromiseにまとめます。録音APIの通信は30秒で中断し、認証更新不能時はマイクを停止します。
ブラウザが前面で動作し続ける試験用モードであり、スリープ・強制終了中の常時録音や最後の未確定区間の保存は保証しません。

音声と安全な再送メタデータはIndexedDBへ最大3セッション、最終更新から24時間だけ保存します。別の先生の未送信データは
日時・時間・内容を表示せず、元の録音者のログインだけを求めます。資格情報は `sessionStorage` だけに保存し、独自ログインの
更新トークンは録音開始前・送信前と録音中の定期更新に使います。自動再送は、利用者が送信を選んだ後に通信が途切れた
`uploading` 状態だけを対象にします。連続モードは開始操作で自動送信に同意した確定済み区間をこの状態にします。
手動モードでは別タブから録音中・停止後確認中のセッションを確定しません。Service Workerはアプリシェルと
`/rec/assets/` だけを扱い、API、認証、音声、非GETリクエストをキャッシュしません。`/rec/` のナビゲーションは
ネットワークを優先し、オフライン時だけキャッシュ済みのシェルへ戻します。
ブラウザが録音中に終了した場合は、最後の端末保存から約2分経過した `recording` 状態を中断済みとして回収し、
次回起動時に利用者が送信または破棄を選べる状態へ戻します。

録音PWAの送信・明示的な再送後は、`SessionStatusMonitor` が受付済みセッションの認証付きGETを約5秒ごとに呼びます。
画面には区間数・完了数・失敗数・状態・不透明な記録IDだけを保持し、音声、ハッシュ、本文は保持しません。
15秒timeout、失敗時の最大60秒バックオフ、画面非表示・オフライン時の中断、復帰直後の確認を備えます。
離脱・録音者や対象の変更は古い応答を無効化します。401で認証更新を1回試し、更新不可ならログインへ戻ります。
403・404は追跡を停止します。終端状態では確認を停止し、記録作成時だけ先生用レビューへのリンクを表示します。
追跡はメモリのみで、ページ再読み込み後や待機へ戻った後は先生用の音声処理状況から確認します。
先生用の一覧は引き続き手動の再読み込みに対応します。いずれも承認・配信や音声の再送は行いません。

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
| `/teacher/audio-jobs/` | `teacher/audio-jobs/+page.svelte` | 録音PWAの処理待ちとクラウド音声処理の安全なメタデータ |
| `/teacher/children/` | `teacher/children/+page.svelte` | 園児・保護者 LINE 連携 |
| `/teacher/voice-consent/` | `teacher/voice-consent/+page.svelte` | 声紋利用への同意・登録・本人確認・削除 |
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
- 外部CDN・フォント・テレメトリは使いません。業務APIは同一オリジンです。
  認証・パスワード設定はブラウザからSupabaseへ直接通信し、録音PWAのtoken更新も同様です。

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


### 先生招待

先生管理は公開認証設定の `teacher_invitations_enabled` がtrueなら登録後に招待APIを呼び、
未連携の先生に送信・再送ボタンを表示します。登録成功と送信失敗を区別し、登録を二重に作りません。
招待リンクの `type=invite` は先生layoutのマウント時に取り出してURLから削除し、ログイン画面を
パスワード設定画面へ切り替えます。パスワード確認後、公開キーと本人トークンでSupabase `/auth/v1/user`
へ直接PUTします。API用のsecret keyはfrontendへ渡しません。

### 記録候補と認証フロー

記録詳細では任意の声紋照合の担当候補を専用APIから追加取得します。取得障害で通常のレビューを
妨げません。候補が存在しても担当セレクトの初期値を変更せず、管理者だけに「候補を引き継ぎ先に選択」を
表示します。この操作は選択だけで、既存の確認付き担当変更操作が必要です。一般の先生は自分の記録の
候補を参照できますが変更できません。声紋設定では本人確認への同意とは別に、同じ園の録音からの照合・
担当候補表示を任意のチェックボックスで選びます。既存同意の読み込み時は追加同意の保存値だけを復元します。

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

Dockerfile は Node.js 24.19.0 の独立したbuild stageで両packageの `npm ci` と検証・ビルドを実行し、
Python runtime stageには `app/frontend_dist/` と `app/recorder_dist/` の生成物だけをコピーします。録音PWAは
`RECORDER_ENABLED=true` のときだけ配信します。実運用環境へのデプロイ確認は別途必要です。

---

## 開発とテスト

録音由来の日誌詳細は任意の園児候補APIを非同期取得し、有効な候補を仮選択します。
候補取得の失敗や遅延は手動レビューを妨げず、手動選択・別日誌への移動後の遅い応答は選択を上書きしません。
録音由来の承認には園児確認チェックを必須とし、園児変更や日誌再読込でチェックを解除します。
実際の園児との紐付けは既存の承認APIだけで確定します。管理者用の園児表示名編集には録音で呼ぶ名前の入力を追加します。

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

録音PWAは別packageとして同じ検証を行います（Playwright実機相当試験は後続です）。

```bash
cd recorder_frontend
npm ci
npm run format:check
npm run lint
npm run check
npm run test:unit
npm run build
```

過去の切り替え結果は [Svelte移行履歴](../svelte-migration-runbook.md)を参照してください。
現在の変更では、上記コマンドを必要な範囲で実行して結果を記録します。
Playwright は API をブラウザで intercept し、次を検査します。

- ホームから各 route への URL 遷移
- `/teacher/review/{recordId}/` の直接表示、reload、Back、Forward
- 先生用の日本語 404
- 保護者 token の hash 除去、再読み込み、無効化
- keyboard、focus、mobile reflow、重大・致命的な axe 違反

FastAPI の配信契約は `tests/test_frontend_delivery.py` で、先生用限定 fallback、guardian の静的配信、
欠損 asset の 404、cache header、外部オリジン参照がないことを検査します。
