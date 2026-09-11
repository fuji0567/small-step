<script lang="ts">
  import { resolve } from '$app/paths';
  import { onMount } from 'svelte';

  let heading: HTMLHeadingElement;

  onMount(() => heading.focus());
</script>

<section class="not-found" aria-labelledby="not-found-heading">
  <p class="not-found__code">404</p>
  <h2 id="not-found-heading" tabindex="-1" bind:this={heading}>
    ページが見つかりません
  </h2>
  <p>URLが正しいか確認するか、ホームから目的の画面を選んでください。</p>
  <a href={resolve('/teacher-next/')}>先生用ホームへ戻る</a>
</section>

<style>
  .not-found {
    display: grid;
    max-width: 40rem;
    gap: var(--ss-space-2);
  }

  .not-found p,
  .not-found h2 {
    margin: 0;
  }

  .not-found__code {
    color: var(--ss-color-text-muted);
    font-size: var(--ss-font-size-heading);
    font-weight: var(--ss-font-weight-bold);
  }

  .not-found h2:focus {
    outline: none;
  }

  .not-found a {
    width: fit-content;
    min-height: 44px;
    box-sizing: border-box;
    padding-block: var(--ss-space-1);
    color: var(--ss-color-action-hover);
    font-weight: var(--ss-font-weight-bold);
    text-underline-offset: 0.25em;
  }

  .not-found a:focus-visible {
    outline: 4px solid var(--ss-color-focus-inner);
    outline-offset: 0;
    box-shadow: 0 0 0 6px var(--ss-color-focus-outer);
  }
</style>
