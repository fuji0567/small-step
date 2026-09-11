<script lang="ts">
  import { resolve } from '$app/paths';
</script>

<svelte:head>
  <title>ホーム | Small Step</title>
</svelte:head>

<section class="home" aria-labelledby="home-heading">
  <h2 id="home-heading">先生用画面</h2>
  <p>今日確認する日誌や通知へ、メニューから移動できます。</p>
  <div class="actions">
    <a href={resolve('/teacher-next/review/')}>レビュー待ちを確認</a>
    <a href={resolve('/teacher-next/notifications/')}>通知状況を確認</a>
  </div>
</section>

<style>
  .home {
    display: grid;
    gap: var(--ss-space-2);
  }

  h2,
  p {
    margin: 0;
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--ss-space-2);
  }

  a {
    display: inline-flex;
    min-height: 44px;
    align-items: center;
    border: 2px solid var(--ss-color-action);
    border-radius: var(--ss-radius-medium);
    padding: var(--ss-space-1) var(--ss-space-2);
    color: var(--ss-color-action-hover);
    background: var(--ss-color-surface);
    font-weight: var(--ss-font-weight-bold);
    text-decoration: none;
  }

  a:hover {
    background: var(--ss-color-action-soft);
  }
</style>
