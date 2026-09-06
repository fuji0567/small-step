# フロントエンド

- 索引: [../architecture.md](../architecture.md)
- 画面一覧と遷移図: [../transition.md](../transition.md)

ビルド工程を持たない素の HTML / CSS / JavaScript です。
FastAPI が `StaticFiles` としてそのまま配信します。

| マウントパス | ディレクトリ | 対象利用者 | 規模 |
| --- | --- | --- | --- |
| `/teacher` | `app/web/` | 先生・先生管理者 | HTML 801 行 / JS 2,874 行 / CSS 2,338 行 |
| `/guardian` | `app/guardian/` | 保護者 | HTML 30 行 / JS 91 行 / CSS 124 行 |

---

## ビルド工程を持たない理由

- 園の PC で `docker compose up` だけで動かせるようにするため、Node のツールチェーンを前提にしない。
- 画面数が十数程度で、フレームワークの導入コストが機能の複雑さに見合わない。
- 依存が増えないぶん、供給網まわりの検討事項も増えない。

代償として `app/web/app.js` が 2,874 行の単一ファイルになっています。
これ以上増えるなら、ビューごとのモジュール分割か軽量フレームワークの導入を検討する分岐点です。

---

## 先生用アプリ（`app/web/`）

### 実行時の構造

`app.js` は単一スコープで、次の順に並んでいます。

| 区画 | 内容 |
| --- | --- |
| 定数 | `apiBase = "/api/v1"`, `accessTokenStorageKey` |
| `state` | 画面が持つ全状態を 1 つのオブジェクトに集約 |
| `elements` | `document.querySelector` の結果をまとめたキャッシュ |
| ヘルパー | `api()`, `fetchWithTimeout()`, `formatDate()`, ラベル変換など |
| 描画関数 | `render*()` — `state` を読んで DOM を組み立てる |
| 取得関数 | `load*()` — API を叩いて `state` を更新し `render*()` を呼ぶ |
| 操作関数 | 承認・却下・発行・無効化など |
| `changeView()` | ビューの表示切り替えと入場時の再取得 |
| イベント登録 | ページ末尾でまとめて `addEventListener` |
| 起動 | `replaceIconPlaceholders()` → `changeView()` → `start()` |

`state` は 1 か所にまとまっています（園、園児、先生、記録、通知、音声ジョブ、監査ログ、
選択中の記録、編集中の園児、現在のビュー、認証情報、`isSchoolAdmin` など）。
状態の置き場所を分散させないことで、フレームワークなしでも追える構造を保っています。

### API 呼び出し

```js
async function api(path, options = {}) { … }
```

- `Authorization: Bearer` はトークンがあるときだけ付与します。
- 成功時は `204` なら `null`、それ以外は JSON を返します。
- 失敗時は `detail` が文字列のときだけそれをエラーメッセージにし、
  それ以外は汎用文言にフォールバックします（想定外のレスポンス本文を画面に出さないため）。
- `error.status` に状態コードを載せます。認証フローの 403 / 404 分岐がこれを使います。
- `fetchWithTimeout()` がタイムアウトを掛け、切れたときは「FastAPI のターミナルを確認して再試行してください」と案内します。

### 認証状態

アクセストークンは `sessionStorage`（キー `small-step.access-token`）に置きます。
タブを閉じれば消えるため、共用端末に残りにくくなります。
ログアウト時は `state` の内容を明示的に空にしてから画面を戻します
（発行済みの招待コードや APIキーが画面に残らないようにするため）。

認証の分岐は [auth.md](auth.md)、画面の状態遷移は [../transition.md](../transition.md) を参照してください。

### アイコン

HTML には `<span class="material-symbols-outlined button-icon">fact_check</span>` のような
プレースホルダを書き、起動時に `replaceIconPlaceholders()` がインライン SVG へ置き換えます。
図形は `localIconPaths` に定義した `<path>` の `d` 属性の配列です。

- **アイコンフォントを外部から読み込みません。** 先生用画面は外部ネットワークへ一切リクエストを出しません。
- フォント読み込み待ちによるアイコンの遅延表示（いわゆる豆腐）が起きません。
- 未定義の名前は `localIconPaths.default` にフォールバックします。
- すべて `aria-hidden="true"` で、意味はテキストラベル側が担います。

動的に作るボタンは `setButtonLabel(button, iconName, label)` でアイコンとラベルを同時に差し替えます。

### スタイル

`styles.css` は `:root` のカスタムプロパティから始まります。

- **文字** … `--font-sans` / `--font-mono`（Web フォントは読み込まず、OS のフォントを優先）
- **余白** … `--space-1` 〜 `--space-8` の 8px スケール
- **色** … `--neutral-*` / `--primary-*` / `--success-*` / `--warning-*` / `--error-*` の意味づけ済みトークン

対応しているメディアクエリ:

| クエリ | 対応内容 |
| --- | --- |
| `max-width: 767px` | スマートフォン向けレイアウト |
| `forced-colors: active` | Windows のハイコントラストモード |
| `prefers-reduced-motion: reduce` | アニメーションの抑制 |

### アクセシビリティ

- 冒頭に「本文へ移動」のスキップリンク、`<main id="main-content" tabindex="-1">`。
- 各ビューは `<section class="app-view" aria-label="...">` で、非表示は `hidden` 属性。
- ナビゲーションの現在地は `aria-current="page"`。
- 非同期に更新される領域（記録一覧、通知一覧、読み込み表示、文字数カウンタなど）は `aria-live="polite"`。
- 通知メッセージは種類に応じて `role="status"` と `role="alert"` を出し分けます。
- 破壊的な操作は `<dialog>` の `showModal()` による確認を挟み、ESC・キャンセル・背景クリックは
  すべて「実行しない」に倒れます。

`index.html` には 83 か所の `aria-*` 属性があります。

---

## 保護者用アプリ（`app/guardian/`）

ログインを持たない単一画面です。園から配布された URL のフラグメントがそのまま資格情報になります。

```
/guardian#ssa_xxxxx
   ↓ archiveToken()
sessionStorage に移す + history.replaceState() で URL から除去
   ↓
GET /api/v1/guardian/archive（Authorization: Bearer ssa_...）
   ↓
配信済みのお知らせ一覧を描画
```

- 失敗時は `sessionStorage` のトークンを破棄し、「園から届いた最新の URL を開いてください」と案内します。
- `<meta name="referrer" content="no-referrer">` を指定し、トークンが外部へ漏れないようにしています。
- 表示するのは配信日時・種別・本文・会話のきっかけだけです。音声も文字起こし原文も扱いません。
- 先生用画面と違い、こちらは Google Fonts（Zen Maru Gothic / Zen Old Mincho）を読み込みます。

---

## 開発時の確認

静的ファイルなのでビルドもウォッチも不要です。API を起動してブラウザで開くだけです。

```bash
uvicorn app.main:app --reload
# 先生用   http://127.0.0.1:8000/teacher
# 保護者用 http://127.0.0.1:8000/guardian
```

`AUTH_MODE=development`（既定）ではログイン画面を経ずに全機能が開き、`isSchoolAdmin` も `true` 扱いです。
権限による表示差分を確認したいときは `AUTH_MODE=supabase` にして実際にログインしてください。
