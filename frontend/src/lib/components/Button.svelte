<script lang="ts">
  import type { Snippet } from 'svelte';
  import type { HTMLButtonAttributes } from 'svelte/elements';

  type Props = Omit<HTMLButtonAttributes, 'children' | 'class' | 'type'> & {
    children: Snippet;
    leading?: Snippet;
    variant?: 'primary' | 'secondary' | 'tertiary' | 'danger';
    size?: 'default' | 'compact';
    loading?: boolean;
    guide?: string;
    type?: 'button' | 'submit' | 'reset';
    class?: string;
  };

  let {
    children,
    leading,
    variant = 'primary',
    size = 'default',
    loading = false,
    guide,
    type = 'button',
    disabled = false,
    class: className = '',
    'aria-describedby': ariaDescribedby,
    ...attributes
  }: Props = $props();

  const componentId = $props.id();
  const guideId = `${componentId}-guide`;
  const buttonDescription = $derived(
    guide
      ? `${ariaDescribedby ? `${ariaDescribedby} ` : ''}${guideId}`
      : ariaDescribedby
  );

  let guideDismissed = $state(false);
  let guidePointerWithin = $state(false);
  let guideFocusWithin = $state(false);

  function handleGuidePointerEnter(): void {
    guidePointerWithin = true;
    guideDismissed = false;
  }

  function handleGuidePointerLeave(): void {
    guidePointerWithin = false;
    if (!guideFocusWithin) guideDismissed = false;
  }

  function handleGuideFocusIn(): void {
    if (!guideFocusWithin) guideDismissed = false;
    guideFocusWithin = true;
  }

  function handleGuideFocusOut(event: FocusEvent): void {
    const nextTarget = event.relatedTarget;
    if (
      nextTarget instanceof Node &&
      (event.currentTarget as HTMLElement).contains(nextTarget)
    )
      return;

    guideFocusWithin = false;
    if (!guidePointerWithin) guideDismissed = false;
  }

  function handleGuideKeydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') guideDismissed = true;
  }
</script>

{#snippet buttonContent()}
  {#if loading}
    <span class="ss-button__spinner" aria-hidden="true"></span>
  {:else if leading}
    <span class="ss-button__leading" aria-hidden="true"
      >{@render leading()}</span
    >
  {/if}
  <span>{@render children()}</span>
{/snippet}

{#if guide}
  <span
    role="presentation"
    class:ss-button-guide--dismissed={guideDismissed}
    class="ss-button-guide"
    onpointerenter={handleGuidePointerEnter}
    onpointerleave={handleGuidePointerLeave}
    onfocusin={handleGuideFocusIn}
    onfocusout={handleGuideFocusOut}
    onkeydown={handleGuideKeydown}
  >
    <button
      {...attributes}
      {type}
      class={`ss-button ss-button--${variant} ss-button--${size} ${className}`.trim()}
      disabled={disabled || loading}
      aria-busy={loading ? 'true' : undefined}
      aria-describedby={buttonDescription}
    >
      {@render buttonContent()}
    </button>
    <span class="ss-button-guide__content" id={guideId} role="tooltip"
      >{guide}</span
    >
  </span>
{:else}
  <button
    {...attributes}
    {type}
    class={`ss-button ss-button--${variant} ss-button--${size} ${className}`.trim()}
    disabled={disabled || loading}
    aria-busy={loading ? 'true' : undefined}
    aria-describedby={buttonDescription}
  >
    {@render buttonContent()}
  </button>
{/if}

<style>
  .ss-button-guide {
    position: relative;
    display: inline-flex;
  }

  .ss-button-guide > .ss-button {
    width: 100%;
  }

  .ss-button-guide__content {
    position: absolute;
    z-index: 100;
    top: calc(100% + var(--ss-space-1, 0.5rem));
    left: 50%;
    width: max-content;
    max-width: min(24rem, calc(100vw - 2rem));
    box-sizing: border-box;
    border-radius: var(--ss-radius-medium, 0.5rem);
    padding: var(--ss-space-1, 0.5rem) var(--ss-space-2, 1rem);
    color: var(--ss-color-surface, #ffffff);
    background: rgb(0 0 0 / 88%);
    background: color-mix(
      in srgb,
      var(--ss-color-focus-outer, #000000) 88%,
      transparent
    );
    font-family: var(--ss-font-sans, sans-serif);
    font-size: var(--ss-font-size-small, 0.875rem);
    font-weight: var(--ss-font-weight-regular, 400);
    line-height: 1.75;
    pointer-events: auto;
    opacity: 0;
    visibility: hidden;
    transform: translateX(-50%);
    transition:
      opacity 120ms linear,
      visibility 0s linear 120ms;
  }

  .ss-button-guide:not(.ss-button-guide--dismissed):hover
    .ss-button-guide__content {
    opacity: 1;
    visibility: visible;
    transition-delay: 600ms;
  }

  .ss-button-guide:not(.ss-button-guide--dismissed):focus-within
    .ss-button-guide__content {
    opacity: 1;
    visibility: visible;
    transition-delay: 0s;
  }

  .ss-button {
    display: inline-flex;
    min-height: 44px;
    align-items: center;
    justify-content: center;
    gap: var(--ss-space-1, 0.5rem);
    border: 2px solid transparent;
    border-radius: var(--ss-radius-medium, 0.5rem);
    padding: var(--ss-space-1, 0.5rem) var(--ss-space-2, 1rem);
    font-family: var(--ss-font-sans, sans-serif);
    font-size: var(--ss-font-size-body, 1rem);
    font-weight: var(--ss-font-weight-bold, 700);
    line-height: 1;
    letter-spacing: 0.02em;
    text-decoration: none;
    cursor: pointer;
  }

  .ss-button--compact {
    padding-inline: var(--ss-space-1, 0.5rem);
    font-size: var(--ss-font-size-small, 0.875rem);
  }

  .ss-button--primary {
    border-color: var(--ss-color-action, #3460fb);
    color: var(--ss-color-surface, #ffffff);
    background: var(--ss-color-action, #3460fb);
  }

  .ss-button--primary:hover:not(:disabled) {
    border-color: var(--ss-color-action-hover, #0031d8);
    background: var(--ss-color-action-hover, #0031d8);
  }

  .ss-button--secondary {
    border-color: var(--ss-color-action, #3460fb);
    color: var(--ss-color-action-hover, #0031d8);
    background: var(--ss-color-surface, #ffffff);
  }

  .ss-button--secondary:hover:not(:disabled),
  .ss-button--tertiary:hover:not(:disabled) {
    background: var(--ss-color-action-soft, #e8f1fe);
  }

  .ss-button--tertiary {
    border-color: transparent;
    color: var(--ss-color-action-hover, #0031d8);
    background: transparent;
    text-decoration: underline;
    text-underline-offset: 0.2em;
  }

  .ss-button--danger {
    border-color: var(--ss-color-error-text, #ce0000);
    color: var(--ss-color-surface, #ffffff);
    background: var(--ss-color-error-text, #ce0000);
  }

  .ss-button--danger:hover:not(:disabled) {
    border-color: var(--ss-color-focus-outer, #000000);
    background: var(--ss-color-focus-outer, #000000);
  }

  .ss-button:focus-visible {
    outline: 4px solid var(--ss-color-focus-inner, #ffd43d);
    outline-offset: 0;
    box-shadow: 0 0 0 6px var(--ss-color-focus-outer, #000000);
  }

  .ss-button:disabled {
    cursor: not-allowed;
    opacity: 0.55;
  }

  .ss-button__leading {
    display: inline-flex;
  }

  .ss-button__spinner {
    width: 1rem;
    height: 1rem;
    border: 2px solid currentColor;
    border-right-color: transparent;
    border-radius: var(--ss-radius-full, 9999px);
    animation: ss-button-spin 0.8s linear infinite;
  }

  @keyframes ss-button-spin {
    to {
      transform: rotate(360deg);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .ss-button-guide__content {
      transition:
        opacity 0s linear,
        visibility 0s linear 120ms;
    }

    .ss-button__spinner {
      animation: none;
    }
  }
</style>
