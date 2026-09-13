<script lang="ts">
  import type { Snippet } from 'svelte';
  import Icon from './Icon.svelte';
  import type { SemanticTone } from './types';

  type Props = {
    tone?: SemanticTone;
    live?: 'off' | 'polite' | 'assertive';
    title?: string;
    children: Snippet;
    class?: string;
  };

  let {
    tone = 'info',
    live = 'polite',
    title,
    children,
    class: className = ''
  }: Props = $props();

  const role = $derived(
    tone === 'error' && live !== 'off' ? 'alert' : 'status'
  );
  const iconName = $derived(tone === 'info' ? 'info' : tone);
</script>

<div
  class={`ss-notice ss-notice--${tone} ${className}`.trim()}
  {role}
  aria-live={role === 'alert' ? undefined : live}
>
  <Icon name={iconName} size={24} decorative={true} />
  <div class="ss-notice__content">
    {#if title}<p class="ss-notice__title">{title}</p>{/if}
    <div class="ss-notice__body">{@render children()}</div>
  </div>
</div>

<style>
  .ss-notice {
    display: flex;
    align-items: flex-start;
    gap: var(--ss-space-1, 0.5rem);
    border: 2px solid var(--ss-color-action, #3460fb);
    border-radius: var(--ss-radius-medium, 0.5rem);
    padding: var(--ss-space-2, 1rem);
    color: var(--ss-color-action-hover, #0031d8);
    background: var(--ss-color-action-soft, #e8f1fe);
    font-family: var(--ss-font-sans, sans-serif);
    font-size: var(--ss-font-size-body, 1rem);
    line-height: 1.7;
  }

  .ss-notice--success {
    border-color: var(--ss-color-success-border, #259d63);
    color: var(--ss-color-success-text, #197a4b);
    background: var(--ss-color-success-background, #e6f5ec);
  }

  .ss-notice--warning {
    border-color: var(--ss-color-warning-border, #af8900);
    color: var(--ss-color-warning-text, #8a6b00);
    background: var(--ss-color-warning-background, #fbf5e0);
  }

  .ss-notice--error {
    border-color: var(--ss-color-error-border, #ec0000);
    color: var(--ss-color-error-text, #ce0000);
    background: var(--ss-color-error-background, #fdeeee);
  }

  .ss-notice__content {
    min-width: 0;
  }

  .ss-notice__title,
  .ss-notice__body :global(:first-child) {
    margin-top: 0;
  }

  .ss-notice__title {
    margin-bottom: var(--ss-space-1, 0.5rem);
    font-weight: var(--ss-font-weight-bold, 700);
  }

  .ss-notice__body :global(:last-child) {
    margin-bottom: 0;
  }
</style>
