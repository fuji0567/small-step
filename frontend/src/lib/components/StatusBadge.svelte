<script lang="ts">
  import type { SemanticTone } from './types';

  type Props = {
    label: string;
    tone?: SemanticTone | 'neutral';
    ariaLabel?: string;
    marker?: boolean;
    live?: boolean;
    class?: string;
  };

  let {
    label,
    tone = 'neutral',
    ariaLabel,
    marker = true,
    live = false,
    class: className = ''
  }: Props = $props();
</script>

<span
  class={`ss-status-badge ss-status-badge--${tone} ${className}`.trim()}
  aria-label={ariaLabel}
  aria-live={live ? 'polite' : undefined}
  role={live ? 'status' : undefined}
>
  {#if marker}<span class="ss-status-badge__marker" aria-hidden="true"
    ></span>{/if}
  <span>{label}</span>
</span>

<style>
  .ss-status-badge {
    display: inline-flex;
    align-items: center;
    gap: var(--ss-space-1, 0.5rem);
    min-height: 1.5rem;
    border: 1px solid var(--ss-color-border, #8c8c8c);
    border-radius: var(--ss-radius-full, 9999px);
    padding-inline: var(--ss-space-1, 0.5rem);
    color: var(--ss-color-text, #1a1a1a);
    background: var(--ss-color-surface, #ffffff);
    font-family: var(--ss-font-sans, sans-serif);
    font-size: var(--ss-font-size-small, 0.875rem);
    font-weight: var(--ss-font-weight-bold, 700);
    line-height: 1.5;
  }

  .ss-status-badge__marker {
    width: 0.5rem;
    height: 0.5rem;
    border-radius: var(--ss-radius-full, 9999px);
    background: var(--ss-color-text-muted, #666666);
  }

  .ss-status-badge--info {
    border-color: var(--ss-color-action, #3460fb);
    color: var(--ss-color-action-hover, #0031d8);
    background: var(--ss-color-action-soft, #e8f1fe);
  }

  .ss-status-badge--info .ss-status-badge__marker {
    background: var(--ss-color-action-hover, #0031d8);
  }

  .ss-status-badge--success {
    border-color: var(--ss-color-success-border, #259d63);
    color: var(--ss-color-success-text, #197a4b);
    background: var(--ss-color-success-background, #e6f5ec);
  }

  .ss-status-badge--success .ss-status-badge__marker {
    background: var(--ss-color-success-text, #197a4b);
  }

  .ss-status-badge--warning {
    border-color: var(--ss-color-warning-border, #af8900);
    color: var(--ss-color-warning-text, #8a6b00);
    background: var(--ss-color-warning-background, #fbf5e0);
  }

  .ss-status-badge--warning .ss-status-badge__marker {
    background: var(--ss-color-warning-text, #8a6b00);
  }

  .ss-status-badge--error {
    border-color: var(--ss-color-error-border, #ec0000);
    color: var(--ss-color-error-text, #ce0000);
    background: var(--ss-color-error-background, #fdeeee);
  }

  .ss-status-badge--error .ss-status-badge__marker {
    background: var(--ss-color-error-text, #ce0000);
  }
</style>
