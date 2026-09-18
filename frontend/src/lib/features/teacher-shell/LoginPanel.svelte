<script lang="ts">
  import { Button, Notice } from '$lib/components';
  import type { TeacherShellState } from './teacher-shell.svelte';

  let { shell }: { shell: TeacherShellState } = $props();
  let email = $state('');
  let password = $state('');
  let submitting = $state(false);
  let passwordConfirm = $state('');
  let validationError = $state<string | null>(null);
  const invitation = $derived(shell.phase === 'password-setup');

  async function submit(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    validationError = null;
    if (invitation && password !== passwordConfirm) {
      validationError = '確認用のパスワードが一致しません。';
      return;
    }
    submitting = true;
    try {
      if (invitation) await shell.completeInvitation(password);
      else await shell.signIn(email.trim(), password);
      password = '';
      passwordConfirm = '';
    } finally {
      submitting = false;
    }
  }
</script>

<svelte:head>
  <title
    >{invitation ? '招待された先生のパスワード設定' : '先生用画面へログイン'} | Small
    Step</title
  >
</svelte:head>

<main class="auth-panel">
  <section aria-labelledby="login-heading">
    <p class="eyebrow">Small Step</p>
    <h1 id="login-heading">
      {invitation ? '招待された先生のパスワード設定' : '先生用画面へログイン'}
    </h1>
    <p>
      {invitation
        ? '自分だけが使うパスワードを設定してください。設定後に先生用画面を開きます。'
        : '登録済みのメールアドレスとパスワードを入力してください。'}
    </p>

    {#if shell.errorMessage}
      <Notice tone="error" title="ログインできませんでした">
        <p>{shell.errorMessage}</p>
      </Notice>
    {/if}
    {#if validationError}<Notice tone="error"><p>{validationError}</p></Notice
      >{/if}

    <form onsubmit={submit}>
      {#if !invitation}<label for="teacher-email">メールアドレス</label>
        <input
          id="teacher-email"
          name="email"
          type="email"
          autocomplete="username"
          required
          bind:value={email}
        />
      {/if}
      <label for="teacher-password">パスワード</label>
      <input
        id="teacher-password"
        name="password"
        type="password"
        autocomplete={invitation ? 'new-password' : 'current-password'}
        minlength={invitation ? 8 : undefined}
        required
        bind:value={password}
      />
      {#if invitation}
        <p>
          8文字以上で設定してください。園の設定によって追加の条件がある場合があります。
        </p>
        <label for="teacher-password-confirm">パスワード（確認）</label>
        <input
          id="teacher-password-confirm"
          type="password"
          autocomplete="new-password"
          required
          bind:value={passwordConfirm}
        />
      {/if}
      <Button type="submit" loading={submitting}
        >{invitation ? 'パスワードを設定して始める' : 'ログイン'}</Button
      >
      {#if invitation}<Button
          variant="secondary"
          disabled={submitting}
          onclick={() => shell.logout()}>ログイン画面へ戻る</Button
        >{/if}
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
    box-sizing: border-box;
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
