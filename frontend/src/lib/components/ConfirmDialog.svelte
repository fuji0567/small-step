<script lang="ts">
  import { tick, type Snippet } from 'svelte';
  import Icon from './Icon.svelte';
  import type { IconName } from './types';

  type Props = {
    open?: boolean;
    title: string;
    description?: string;
    confirmLabel?: string;
    cancelLabel?: string;
    tone?: 'default' | 'danger';
    icon?: IconName;
    busy?: boolean;
    children?: Snippet;
    onConfirm?: () => void | Promise<void>;
    onCancel?: () => void;
  };

  let {
    open = $bindable(false),
    title,
    description,
    confirmLabel = '実行する',
    cancelLabel = 'キャンセル',
    tone = 'default',
    icon,
    busy = false,
    children,
    onConfirm,
    onCancel
  }: Props = $props();

  const uid = $props.id();
  const titleId = `${uid}-title`;
  const descriptionId = `${uid}-description`;

  let dialog: HTMLDialogElement;
  let cancelButton: HTMLButtonElement;
  let previouslyFocused: HTMLElement | null = null;

  function showDialog(): void {
    if (dialog.open) return;

    try {
      dialog.showModal();
    } catch {
      dialog.setAttribute('open', '');
    }
  }

  function closeDialog(): void {
    if (!dialog.open) return;

    try {
      dialog.close();
    } catch {
      dialog.removeAttribute('open');
    }
  }

  function restoreFocus(): void {
    const target = previouslyFocused;
    previouslyFocused = null;
    target?.focus();
  }

  function requestCancel(): void {
    if (busy) return;
    open = false;
    onCancel?.();
  }

  async function requestConfirm(): Promise<void> {
    if (busy) return;
    await onConfirm?.();
    open = false;
  }

  function handleCancel(event: Event): void {
    event.preventDefault();
    requestCancel();
  }

  function handleBackdropClick(event: MouseEvent): void {
    if (event.target === dialog) requestCancel();
  }

  $effect(() => {
    if (!dialog) return;

    if (open) {
      previouslyFocused ??=
        document.activeElement instanceof HTMLElement
          ? document.activeElement
          : null;
      showDialog();
      void tick().then(() => cancelButton?.focus());
    } else {
      closeDialog();
      queueMicrotask(restoreFocus);
    }
  });
</script>

<dialog
  bind:this={dialog}
  class="ss-confirm-dialog"
  aria-labelledby={titleId}
  aria-describedby={description ? descriptionId : undefined}
  aria-busy={busy ? 'true' : undefined}
  oncancel={handleCancel}
  onclick={handleBackdropClick}
>
  <div class="ss-confirm-dialog__panel">
    <div class="ss-confirm-dialog__heading">
      {#if icon}
        <Icon name={icon} size={24} decorative={true} />
      {/if}
      <h2 id={titleId}>{title}</h2>
    </div>

    {#if description}<p id={descriptionId}>{description}</p>{/if}
    {#if children}<div class="ss-confirm-dialog__body">
        {@render children()}
      </div>{/if}

    <div class="ss-confirm-dialog__actions">
      <button
        bind:this={cancelButton}
        class="ss-confirm-dialog__button ss-confirm-dialog__button--cancel"
        type="button"
        disabled={busy}
        onclick={requestCancel}
      >
        {cancelLabel}
      </button>
      <button
        class:ss-confirm-dialog__button--danger={tone === 'danger'}
        class="ss-confirm-dialog__button ss-confirm-dialog__button--confirm"
        type="button"
        disabled={busy}
        aria-busy={busy ? 'true' : undefined}
        onclick={requestConfirm}
      >
        {busy ? '処理中です' : confirmLabel}
      </button>
    </div>
  </div>
</dialog>

<style>
  .ss-confirm-dialog {
    width: min(36rem, calc(100% - 2rem));
    max-height: calc(100% - 2rem);
    border: 0;
    border-radius: var(--ss-radius-large, 0.75rem);
    padding: 0;
    color: var(--ss-color-text, #1a1a1a);
    background: transparent;
    font-family: var(--ss-font-sans, sans-serif);
  }

  .ss-confirm-dialog::backdrop {
    background: rgb(0 0 0 / 56%);
  }

  .ss-confirm-dialog__panel {
    display: grid;
    gap: var(--ss-space-2, 1rem);
    border: 2px solid var(--ss-color-border, #8c8c8c);
    border-radius: var(--ss-radius-large, 0.75rem);
    padding: var(--ss-space-3, 1.5rem);
    background: var(--ss-color-surface, #ffffff);
  }

  .ss-confirm-dialog__heading {
    display: flex;
    align-items: flex-start;
    gap: var(--ss-space-1, 0.5rem);
  }

  h2,
  p {
    margin: 0;
  }

  h2 {
    font-size: var(--ss-font-size-heading, 1.5rem);
    line-height: 1.5;
  }

  p,
  .ss-confirm-dialog__body {
    max-width: 40em;
    font-size: var(--ss-font-size-body, 1rem);
    line-height: 1.7;
  }

  .ss-confirm-dialog__actions {
    display: flex;
    flex-wrap: wrap;
    justify-content: flex-end;
    gap: var(--ss-space-2, 1rem);
  }

  .ss-confirm-dialog__button {
    min-height: 44px;
    border: 2px solid var(--ss-color-action, #3460fb);
    border-radius: var(--ss-radius-medium, 0.5rem);
    padding: var(--ss-space-1, 0.5rem) var(--ss-space-2, 1rem);
    font: inherit;
    font-weight: var(--ss-font-weight-bold, 700);
    line-height: 1;
    cursor: pointer;
  }

  .ss-confirm-dialog__button--cancel {
    color: var(--ss-color-action-hover, #0031d8);
    background: var(--ss-color-surface, #ffffff);
  }

  .ss-confirm-dialog__button--confirm {
    color: var(--ss-color-surface, #ffffff);
    background: var(--ss-color-action, #3460fb);
  }

  .ss-confirm-dialog__button--danger {
    border-color: var(--ss-color-error-text, #ce0000);
    background: var(--ss-color-error-text, #ce0000);
  }

  .ss-confirm-dialog__button:hover:not(:disabled) {
    border-color: var(--ss-color-action-hover, #0031d8);
  }

  .ss-confirm-dialog__button--cancel:hover:not(:disabled) {
    background: var(--ss-color-action-soft, #e8f1fe);
  }

  .ss-confirm-dialog__button--confirm:hover:not(:disabled) {
    background: var(--ss-color-action-hover, #0031d8);
  }

  .ss-confirm-dialog__button:focus-visible {
    outline: 4px solid var(--ss-color-focus-inner, #ffd43d);
    outline-offset: 0;
    box-shadow: 0 0 0 6px var(--ss-color-focus-outer, #000000);
  }

  .ss-confirm-dialog__button:disabled {
    cursor: not-allowed;
    opacity: 0.55;
  }
</style>
