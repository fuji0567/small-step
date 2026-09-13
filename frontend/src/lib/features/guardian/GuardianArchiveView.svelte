<script lang="ts">
  import { replaceState } from '$app/navigation';
  import { resolve } from '$app/paths';
  import type { Pathname } from '$app/types';
  import { onMount } from 'svelte';

  import { Loading, Notice } from '$lib/components';
  import '$lib/design/tokens.css';

  import { createGuardianArchiveClient, loadGuardianArchive } from './api';
  import { consumeGuardianArchiveToken } from './token';
  import type {
    GuardianArchiveLoadResult,
    GuardianArchiveNotification
  } from './types';

  type ViewState =
    | { status: 'loading' }
    | { status: 'missing-link' }
    | GuardianArchiveLoadResult;

  let state = $state<ViewState>({ status: 'loading' });
  let started = false;
  let requestController: AbortController | null = null;

  function formatDate(value: string): string {
    return new Intl.DateTimeFormat('ja-JP', {
      dateStyle: 'long',
      timeStyle: 'short'
    }).format(new Date(value));
  }

  function categoryLabel(category: 'growth' | 'injury'): string {
    return category === 'injury' ? 'けがの記録' : '成長の記録';
  }

  function notificationKey(
    notification: GuardianArchiveNotification,
    index: number
  ): string {
    return `${notification.delivered_at}:${notification.category}:${index}`;
  }

  onMount(() => {
    const start = () => {
      if (started) return;
      started = true;

      const token = consumeGuardianArchiveToken({
        location: window.location,
        replaceUrl: (pathname) =>
          replaceState(resolve(pathname as Pathname), {}),
        sessionStorage: window.sessionStorage
      });
      if (!token) {
        state = { status: 'missing-link' };
        return;
      }

      requestController = new AbortController();
      const client = createGuardianArchiveClient(token);
      void loadGuardianArchive(
        client,
        window.sessionStorage,
        requestController.signal
      ).then((result) => {
        if (result.status !== 'cancelled') state = result;
      });
    };

    const timer = globalThis.setTimeout(start, 0);
    return () => {
      globalThis.clearTimeout(timer);
      requestController?.abort();
    };
  });
</script>

<main class="archive-shell">
  <header class="archive-header">
    <p class="archive-brand">SMALL STEP</p>
    <h1>配信アーカイブ</h1>
    <p>園から届いたお知らせを確認できます。</p>
  </header>

  <section class="archive-card" aria-labelledby="archive-content-title">
    {#if state.status === 'loading'}
      <h2 id="archive-content-title" class="visually-hidden">読み込み状況</h2>
      <Loading label="お知らせを読み込んでいます" />
    {:else if state.status === 'missing-link'}
      <h2 id="archive-content-title" class="visually-hidden">エラー</h2>
      <Notice tone="error" live="assertive" title="このアーカイブは開けません">
        <p>URLが見つかりません。園から届いた最新のURLを開いてください。</p>
      </Notice>
    {:else if state.status === 'invalid-link'}
      <h2 id="archive-content-title" class="visually-hidden">エラー</h2>
      <Notice tone="error" live="assertive" title="このアーカイブは開けません">
        <p>
          URLの有効期限が切れたか、無効になっています。園へ最新のURLをご確認ください。
        </p>
      </Notice>
    {:else if state.status === 'network-error'}
      <h2 id="archive-content-title" class="visually-hidden">エラー</h2>
      <Notice
        tone="error"
        live="assertive"
        title="お知らせを読み込めませんでした"
      >
        <p>
          通信に失敗しました。時間をおいて、もう一度この画面を開いてください。
        </p>
      </Notice>
    {:else if state.status === 'success'}
      {@const archive = state.archive}
      <h2 id="archive-content-title">
        {archive.child_display_name}さんのお知らせ
      </h2>
      <p class="archive-expiration">
        このURLの有効期限: {formatDate(archive.expires_at)}
      </p>

      {#if archive.notifications.length === 0}
        <Notice tone="info" title="お知らせはまだありません">
          <p>送信済みのお知らせはまだありません。</p>
        </Notice>
      {:else}
        <div class="archive-list">
          {#each archive.notifications as notification, index (notificationKey(notification, index))}
            <article class="archive-item">
              <p class="archive-meta">
                <time datetime={notification.delivered_at}
                  >{formatDate(notification.delivered_at)}</time
                >
                <span aria-hidden="true"> / </span>
                <span>{categoryLabel(notification.category)}</span>
              </p>
              <p class="archive-summary">{notification.summary}</p>
              {#if notification.conversation_prompt}
                <p class="archive-prompt">
                  <span class="prompt-label">おうちでの会話のきっかけ</span>
                  {notification.conversation_prompt}
                </p>
              {/if}
            </article>
          {/each}
        </div>
      {/if}
    {/if}
  </section>

  <p class="archive-footer">
    この画面を閉じると、次回は園から届いたURLをもう一度開く必要があります。
  </p>
</main>

<style>
  .archive-shell {
    width: min(calc(100% - var(--ss-space-4)), 46rem);
    margin: 0 auto;
    padding: var(--ss-space-5) 0;
    color: var(--ss-color-text);
    font-family: var(--ss-font-sans);
  }

  .archive-header {
    margin-bottom: var(--ss-space-3);
  }

  .archive-brand {
    margin: 0 0 var(--ss-space-1);
    color: var(--ss-color-action-hover);
    font-size: var(--ss-font-size-small);
    font-weight: var(--ss-font-weight-bold);
    letter-spacing: 0.125em;
  }

  h1,
  h2 {
    margin: 0;
    line-height: 1.5;
  }

  h1 {
    font-size: clamp(
      var(--ss-font-size-heading),
      7vw,
      var(--ss-font-size-display)
    );
  }

  h2 {
    font-size: var(--ss-font-size-heading);
  }

  .archive-header > p:last-child {
    margin: var(--ss-space-1) 0 0;
    color: var(--ss-color-text-muted);
    line-height: 1.75;
  }

  .archive-card {
    border: 1px solid var(--ss-color-border);
    border-radius: var(--ss-radius-large);
    padding: var(--ss-space-4);
    background: var(--ss-color-surface);
  }

  .archive-expiration {
    margin: var(--ss-space-1) 0 var(--ss-space-3);
    color: var(--ss-color-text-muted);
    font-size: var(--ss-font-size-small);
    line-height: 1.75;
  }

  .archive-list {
    display: grid;
    gap: var(--ss-space-2);
  }

  .archive-item {
    border: 1px solid var(--ss-color-border);
    border-left: var(--ss-space-1) solid var(--ss-color-warning-border);
    border-radius: var(--ss-radius-medium);
    padding: var(--ss-space-2);
    background: var(--ss-color-surface);
  }

  .archive-item p {
    margin: 0;
  }

  .archive-meta {
    color: var(--ss-color-text-muted);
    font-size: var(--ss-font-size-small);
    line-height: 1.75;
  }

  .archive-summary {
    margin-top: var(--ss-space-1) !important;
    line-height: 1.75;
  }

  .archive-prompt {
    margin-top: var(--ss-space-2) !important;
    border-radius: var(--ss-radius-medium);
    padding: var(--ss-space-2);
    color: var(--ss-color-action-hover);
    background: var(--ss-color-action-soft);
    line-height: 1.75;
  }

  .prompt-label {
    display: block;
    margin-bottom: var(--ss-space-1);
    font-size: var(--ss-font-size-small);
    font-weight: var(--ss-font-weight-bold);
  }

  .archive-footer {
    margin: var(--ss-space-2) 0 0;
    color: var(--ss-color-text-muted);
    font-size: var(--ss-font-size-small);
    line-height: 1.75;
  }

  .visually-hidden {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
    white-space: nowrap;
    clip-path: inset(50%);
  }

  @media (max-width: 35rem) {
    .archive-shell {
      width: min(calc(100% - var(--ss-space-3)), 46rem);
      padding: var(--ss-space-4) 0;
    }

    .archive-card {
      padding: var(--ss-space-2);
    }
  }
</style>
