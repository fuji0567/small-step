<script lang="ts">
  type Props = {
    active?: boolean;
    label?: string;
    mode?: 'inline' | 'fixed';
    class?: string;
  };

  let {
    active = true,
    label = '読み込み中です',
    mode = 'inline',
    class: className = ''
  }: Props = $props();
</script>

{#if active}
  <div
    class={`ss-loading ss-loading--${mode} ${className}`.trim()}
    role="status"
    aria-live="polite"
    aria-label={label}
  >
    <span class="ss-loading__spinner" aria-hidden="true"></span>
    <span>{label}</span>
  </div>
{/if}

<style>
  .ss-loading {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--ss-space-1, 0.5rem);
    color: var(--ss-color-text, #1a1a1a);
    font-family: var(--ss-font-sans, sans-serif);
    font-size: var(--ss-font-size-body, 1rem);
    font-weight: var(--ss-font-weight-bold, 700);
    line-height: 1.5;
  }

  .ss-loading--fixed {
    position: fixed;
    z-index: 1000;
    inset: 0;
    padding: var(--ss-space-3, 1.5rem);
    background: rgb(255 255 255 / 92%);
  }

  .ss-loading__spinner {
    width: 1.5rem;
    height: 1.5rem;
    border: 3px solid var(--ss-color-border, #8c8c8c);
    border-top-color: var(--ss-color-action-hover, #0031d8);
    border-radius: var(--ss-radius-full, 9999px);
    animation: ss-loading-spin 0.8s linear infinite;
  }

  @keyframes ss-loading-spin {
    to {
      transform: rotate(360deg);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .ss-loading__spinner {
      animation: none;
    }
  }
</style>
