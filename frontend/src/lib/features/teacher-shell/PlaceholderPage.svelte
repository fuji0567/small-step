<script lang="ts">
  let {
    title,
    description
  }: {
    title: string;
    description: string;
  } = $props();
</script>

<section class="placeholder" aria-labelledby="feature-heading">
  <h2 id="feature-heading">{title}</h2>
  <p>{description}</p>
  <p>この画面の機能は、移行手順に沿って順次追加します。</p>
</section>

<style>
  .placeholder {
    display: grid;
    gap: var(--ss-space-2);
    max-width: 48rem;
    border: 1px solid var(--ss-color-border);
    border-radius: var(--ss-radius-large);
    padding: var(--ss-space-3);
    background: var(--ss-color-surface);
  }

  h2,
  p {
    margin: 0;
  }
</style>
