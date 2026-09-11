<script lang="ts">
  import { Button, Notice } from '$lib/components';
  import type { TeacherShellState } from './teacher-shell.svelte';

  let { shell }: { shell: TeacherShellState } = $props();
  let email = $state('');
  let password = $state('');
  let submitting = $state(false);

  async function submit(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    submitting = true;
    try {
      await shell.signIn(email.trim(), password);
      password = '';
    } finally {
      submitting = false;
    }
  }
</script>

<main class="auth-panel">
  <section aria-labelledby="login-heading">
    <p class="eyebrow">Small Step</p>
    <h1 id="login-heading">先生用画面へログイン</h1>
    <p>登録済みのメールアドレスとパスワードを入力してください。</p>

    {#if shell.errorMessage}
      <Notice tone="error" title="ログインできませんでした">
        <p>{shell.errorMessage}</p>
      </Notice>
    {/if}

    <form onsubmit={submit}>
      <label for="teacher-email">メールアドレス</label>
      <input
        id="teacher-email"
        name="email"
        type="email"
        autocomplete="username"
        required
        bind:value={email}
      />
      <label for="teacher-password">パスワード</label>
      <input
        id="teacher-password"
        name="password"
        type="password"
        autocomplete="current-password"
        required
        bind:value={password}
      />
      <Button type="submit" loading={submitting}>ログイン</Button>
    </form>
  </section>
</main>

<style>
  .auth-panel {
    display: grid;
    min-height: 100vh;
    place-items: center;
    padding: var(--ss-space-3);
    background: var(--ss-color-page);
  }

  section {
    display: grid;
    width: min(100%, 32rem);
    gap: var(--ss-space-2);
    border: 1px solid var(--ss-color-border);
    border-radius: var(--ss-radius-large);
    padding: var(--ss-space-4);
    background: var(--ss-color-surface);
  }

  h1,
  p {
    margin: 0;
  }

  .eyebrow,
  label {
    font-weight: var(--ss-font-weight-bold);
  }

  .eyebrow {
    color: var(--ss-color-text-muted);
  }

  form {
    display: grid;
    gap: var(--ss-space-2);
  }

  input {
    min-height: 44px;
    box-sizing: border-box;
    border: 2px solid var(--ss-color-border);
    border-radius: var(--ss-radius-medium);
    padding: var(--ss-space-1) var(--ss-space-2);
    font: inherit;
  }

  input:focus-visible {
    outline: 4px solid var(--ss-color-focus-inner);
    outline-offset: 0;
    box-shadow: 0 0 0 6px var(--ss-color-focus-outer);
  }
</style>
