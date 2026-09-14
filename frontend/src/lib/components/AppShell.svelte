<script lang="ts">
  import { resolve } from '$app/paths';
  import type { Snippet } from 'svelte';
  import Icon from './Icon.svelte';
  import Loading from './Loading.svelte';
  import type { AppShellNavItem } from './types';

  type Props = {
    title: string;
    eyebrow?: string;
    description?: string;
    navLabel?: string;
    navItems: AppShellNavItem[];
    currentPath: string;
    busy?: boolean;
    headerActions?: Snippet;
    toolbar?: Snippet;
    children: Snippet;
  };

  let {
    title,
    eyebrow,
    description,
    navLabel = '先生用メニュー',
    navItems,
    currentPath,
    busy = false,
    headerActions,
    toolbar,
    children
  }: Props = $props();

  const componentId = $props.id();

  function isCurrent(item: AppShellNavItem): boolean {
    const href = resolve(item.href);
    if (currentPath === href) return true;
    if (href === resolve('/teacher/')) return false;
    return currentPath.startsWith(href);
  }

  function navGuideId(index: number): string {
    return `${componentId}-nav-guide-${index}`;
  }

  function dismissibleGuide(node: HTMLElement) {
    let pointerWithin = false;
    let focusWithin = false;

    function clearDismissed(): void {
      node.classList.remove('ss-app-shell__nav-item--guide-dismissed');
    }

    function handlePointerEnter(): void {
      pointerWithin = true;
      clearDismissed();
    }

    function handlePointerLeave(): void {
      pointerWithin = false;
      if (!focusWithin) clearDismissed();
    }

    function handleFocusIn(): void {
      if (!focusWithin) clearDismissed();
      focusWithin = true;
    }

    function handleFocusOut(event: FocusEvent): void {
      const nextTarget = event.relatedTarget;
      if (nextTarget instanceof Node && node.contains(nextTarget)) return;
      focusWithin = false;
      if (!pointerWithin) clearDismissed();
    }

    function handleKeydown(event: KeyboardEvent): void {
      if (event.key === 'Escape') {
        node.classList.add('ss-app-shell__nav-item--guide-dismissed');
      }
    }

    node.addEventListener('pointerenter', handlePointerEnter);
    node.addEventListener('pointerleave', handlePointerLeave);
    node.addEventListener('focusin', handleFocusIn);
    node.addEventListener('focusout', handleFocusOut);
    node.addEventListener('keydown', handleKeydown);

    return {
      destroy(): void {
        node.removeEventListener('pointerenter', handlePointerEnter);
        node.removeEventListener('pointerleave', handlePointerLeave);
        node.removeEventListener('focusin', handleFocusIn);
        node.removeEventListener('focusout', handleFocusOut);
        node.removeEventListener('keydown', handleKeydown);
      }
    };
  }
</script>

<a class="ss-app-shell__skip-link" href="#main-content">本文へ移動</a>

<div class="ss-app-shell">
  <header class="ss-app-shell__header">
    <div>
      {#if eyebrow}<p class="ss-app-shell__eyebrow">{eyebrow}</p>{/if}
      <h1>{title}</h1>
    </div>
    {#if description}<p class="ss-app-shell__description">{description}</p>{/if}
    {#if headerActions}<div class="ss-app-shell__header-actions">
        {@render headerActions()}
      </div>{/if}
  </header>

  {#if toolbar}<section class="ss-app-shell__toolbar" aria-label="表示設定">
      {@render toolbar()}
    </section>{/if}

  <div class="ss-app-shell__body">
    <nav class="ss-app-shell__nav" aria-label={navLabel}>
      <ul>
        {#each navItems as item, index (item.href)}
          <li>
            {#if item.guide}
              <span class="ss-app-shell__nav-item" use:dismissibleGuide>
                <a
                  href={resolve(item.href)}
                  aria-current={isCurrent(item) ? 'page' : undefined}
                  aria-describedby={navGuideId(index)}
                >
                  {#if item.icon}<Icon
                      name={item.icon}
                      decorative={true}
                    />{/if}
                  <span>{item.label}</span>
                  {#if item.badge}
                    <span
                      class={`ss-app-shell__badge ss-app-shell__badge--${item.badgeTone ?? 'default'}`}
                      aria-label={item.badgeAriaLabel}>{item.badge}</span
                    >
                  {/if}
                </a>
                <span
                  class="ss-app-shell__guide"
                  id={navGuideId(index)}
                  role="tooltip">{item.guide}</span
                >
              </span>
            {:else}
              <a
                href={resolve(item.href)}
                aria-current={isCurrent(item) ? 'page' : undefined}
              >
                {#if item.icon}<Icon name={item.icon} decorative={true} />{/if}
                <span>{item.label}</span>
                {#if item.badge}
                  <span
                    class={`ss-app-shell__badge ss-app-shell__badge--${item.badgeTone ?? 'default'}`}
                    aria-label={item.badgeAriaLabel}>{item.badge}</span
                  >
                {/if}
              </a>
            {/if}
          </li>
        {/each}
      </ul>
    </nav>

    <main
      id="main-content"
      class="ss-app-shell__main"
      tabindex="-1"
      aria-busy={busy ? 'true' : undefined}
    >
      {#if busy}<Loading label="読み込み中です" />{/if}
      {@render children()}
    </main>
  </div>
</div>

<style>
  .ss-app-shell__skip-link {
    position: fixed;
    z-index: 2000;
    top: var(--ss-space-2, 1rem);
    left: var(--ss-space-2, 1rem);
    transform: translateY(-200%);
    border: 2px solid var(--ss-color-focus-outer, #000000);
    border-radius: var(--ss-radius-small, 0.25rem);
    padding: var(--ss-space-1, 0.5rem) var(--ss-space-2, 1rem);
    color: var(--ss-color-focus-outer, #000000);
    background: var(--ss-color-focus-inner, #ffd43d);
    font-weight: var(--ss-font-weight-bold, 700);
  }

  .ss-app-shell__skip-link:focus {
    transform: translateY(0);
  }

  .ss-app-shell {
    min-height: 100vh;
    color: var(--ss-color-text, #1a1a1a);
    background: var(--ss-color-page, #f2f2f2);
    font-family: var(--ss-font-sans, sans-serif);
  }

  .ss-app-shell__header {
    display: flex;
    align-items: center;
    gap: var(--ss-space-3, 1.5rem);
    border-bottom: 1px solid var(--ss-color-border, #8c8c8c);
    padding: var(--ss-space-2, 1rem) var(--ss-space-3, 1.5rem);
    background: var(--ss-color-surface, #ffffff);
  }

  .ss-app-shell__header > :first-child {
    margin-right: auto;
  }

  .ss-app-shell__eyebrow,
  .ss-app-shell__description,
  h1 {
    margin: 0;
  }

  .ss-app-shell__eyebrow {
    color: var(--ss-color-text-muted, #666666);
    font-size: var(--ss-font-size-small, 0.875rem);
    font-weight: var(--ss-font-weight-bold, 700);
    line-height: 1.5;
  }

  h1 {
    font-size: var(--ss-font-size-heading, 1.5rem);
    line-height: 1.5;
  }

  .ss-app-shell__description {
    max-width: 40em;
    font-size: var(--ss-font-size-body, 1rem);
    line-height: 1.7;
  }

  .ss-app-shell__header-actions {
    display: flex;
    gap: var(--ss-space-1, 0.5rem);
  }

  .ss-app-shell__toolbar {
    border-bottom: 1px solid var(--ss-color-border, #8c8c8c);
    padding: var(--ss-space-2, 1rem) var(--ss-space-3, 1.5rem);
    background: var(--ss-color-surface, #ffffff);
  }

  .ss-app-shell__body {
    display: grid;
    grid-template-columns: minmax(13rem, 17rem) minmax(0, 1fr);
    align-items: start;
  }

  .ss-app-shell__nav {
    position: sticky;
    top: 0;
    min-width: 0;
    padding: var(--ss-space-2, 1rem);
  }

  .ss-app-shell__nav ul {
    display: grid;
    gap: var(--ss-space-1, 0.5rem);
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .ss-app-shell__nav a {
    display: flex;
    min-height: 44px;
    align-items: center;
    gap: var(--ss-space-1, 0.5rem);
    border: 2px solid transparent;
    border-radius: var(--ss-radius-medium, 0.5rem);
    padding: var(--ss-space-1, 0.5rem) var(--ss-space-2, 1rem);
    color: var(--ss-color-text, #1a1a1a);
    font-size: var(--ss-font-size-body, 1rem);
    font-weight: var(--ss-font-weight-bold, 700);
    line-height: 1.5;
    text-decoration: none;
  }

  .ss-app-shell__nav a:hover {
    color: var(--ss-color-action-hover, #0031d8);
    background: var(--ss-color-action-soft, #e8f1fe);
  }

  .ss-app-shell__nav a[aria-current='page'] {
    border-color: var(--ss-color-action, #3460fb);
    color: var(--ss-color-action-hover, #0031d8);
    background: var(--ss-color-action-soft, #e8f1fe);
  }

  .ss-app-shell__nav a:focus-visible,
  .ss-app-shell__skip-link:focus-visible {
    outline: 4px solid var(--ss-color-focus-inner, #ffd43d);
    outline-offset: 0;
    box-shadow: 0 0 0 6px var(--ss-color-focus-outer, #000000);
  }

  .ss-app-shell__nav-item {
    position: relative;
    display: block;
  }

  .ss-app-shell__guide {
    position: absolute;
    z-index: 10;
    top: 50%;
    left: calc(100% + var(--ss-space-1, 0.5rem));
    width: max-content;
    max-width: min(20rem, calc(100vw - 2rem));
    box-sizing: border-box;
    border-radius: var(--ss-radius-medium, 0.5rem);
    padding: var(--ss-space-1, 0.5rem) var(--ss-space-2, 1rem);
    color: var(--ss-color-surface, #ffffff);
    background: var(--ss-color-focus-outer, #000000);
    font-size: var(--ss-font-size-small, 0.875rem);
    font-weight: var(--ss-font-weight-regular, 400);
    line-height: 1.75;
    pointer-events: auto;
    opacity: 0;
    visibility: hidden;
    transform: translateY(-50%);
    transition:
      opacity 120ms linear,
      visibility 0s linear 120ms;
  }

  .ss-app-shell__nav-item:not(.ss-app-shell__nav-item--guide-dismissed):hover
    .ss-app-shell__guide,
  .ss-app-shell__nav-item:not(
      .ss-app-shell__nav-item--guide-dismissed
    ):focus-within
    .ss-app-shell__guide {
    opacity: 1;
    visibility: visible;
    transition-delay: 0s;
  }

  .ss-app-shell__badge {
    display: inline-flex;
    flex: 0 0 auto;
    align-items: center;
    margin-left: auto;
    border: 1px solid var(--ss-color-border, #8c8c8c);
    border-radius: var(--ss-radius-full, 9999px);
    padding-inline: var(--ss-space-1, 0.5rem);
    color: var(--ss-color-text, #1a1a1a);
    background: var(--ss-color-surface, #ffffff);
    font-size: var(--ss-font-size-small, 0.875rem);
    line-height: 1.5;
    white-space: nowrap;
  }

  .ss-app-shell__badge--warning {
    border-color: var(--ss-color-warning-border, #af8900);
    color: var(--ss-color-warning-text, #8a6b00);
    background: var(--ss-color-warning-background, #fbf5e0);
  }

  .ss-app-shell__main {
    min-width: 0;
    padding: var(--ss-space-4, 2rem);
  }

  @media (max-width: 47.999rem) {
    .ss-app-shell__header {
      align-items: flex-start;
      flex-direction: column;
      padding: var(--ss-space-2, 1rem);
    }

    .ss-app-shell__description {
      max-width: none;
    }

    .ss-app-shell__toolbar {
      padding: var(--ss-space-2, 1rem);
    }

    .ss-app-shell__body {
      display: block;
    }

    .ss-app-shell__nav {
      position: static;
      overflow-x: auto;
      padding: var(--ss-space-1, 0.5rem) var(--ss-space-2, 1rem);
    }

    .ss-app-shell__nav ul {
      display: flex;
      width: max-content;
    }

    .ss-app-shell__main {
      padding: var(--ss-space-2, 1rem);
    }

    .ss-app-shell__guide {
      position: fixed;
      top: auto;
      right: var(--ss-space-2, 1rem);
      bottom: var(--ss-space-2, 1rem);
      left: var(--ss-space-2, 1rem);
      width: auto;
      max-width: none;
      transform: none;
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .ss-app-shell__guide {
      transition: none;
    }
  }
</style>
