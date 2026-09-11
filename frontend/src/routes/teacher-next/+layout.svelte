<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import { resolve } from '$app/paths';
  import { afterNavigate } from '$app/navigation';
  import { initializeTeacherSession } from '$lib/auth';
  import { AppShell, Button, Loading, Notice } from '$lib/components';
  import {
    BootstrapPanel,
    canAccessTeacherRoute,
    LoginPanel,
    provideTeacherShell,
    TeacherShellState,
    teacherNavItems,
    teacherPageTitle
  } from '$lib/features/teacher-shell';
  import { onMount, type Snippet } from 'svelte';

  let { children }: { children: Snippet } = $props();
  const shell = new TeacherShellState((input, init) =>
    globalThis.fetch(input, init)
  );
  provideTeacherShell(shell);

  let session = $state<ReturnType<typeof initializeTeacherSession>>(null);
  let redirectedFromAdmin = $state(false);
  const currentPath = $derived(page.url.pathname);
  const title = $derived(teacherPageTitle(currentPath));
  const navItems = $derived(teacherNavItems(shell.isSchoolAdmin));
  const adminRouteDenied = $derived(
    shell.phase === 'ready' &&
      !canAccessTeacherRoute(currentPath, shell.isSchoolAdmin)
  );

  onMount(() => {
    session = initializeTeacherSession();
    void shell.initialize(session);
  });

  $effect(() => {
    if (!adminRouteDenied) return;
    redirectedFromAdmin = true;
    void goto(resolve('/teacher-next/'), { replaceState: true });
  });

  afterNavigate(() => {
    globalThis.requestAnimationFrame(() => {
      document.querySelector<HTMLElement>('#main-content')?.focus();
    });
  });

  async function retryInitialization(): Promise<void> {
    await shell.initialize(session);
  }

  function logout(): void {
    shell.logout();
    redirectedFromAdmin = false;
    void goto(resolve('/teacher-next/'), { replaceState: true });
  }
</script>

{#if shell.phase === 'initializing'}
  <Loading mode="fixed" label="先生用画面を準備しています" />
{:else if shell.phase === 'login'}
  <LoginPanel {shell} />
{:else if shell.phase === 'bootstrap'}
  <BootstrapPanel {shell} />
{:else if shell.phase === 'fatal'}
  <main class="startup-error">
    <h1>先生用画面を開けません</h1>
    <Notice tone="error" title="初期化に失敗しました">
      <p>{shell.errorMessage ?? '通信に失敗しました。'}</p>
    </Notice>
    <Button onclick={retryInitialization}>再試行</Button>
  </main>
{:else if adminRouteDenied}
  <Loading mode="fixed" label="利用できる画面へ移動しています" />
{:else}
  {#snippet headerActions()}
    {#if shell.canLogout}
      <Button variant="secondary" onclick={logout}>ログアウト</Button>
    {/if}
  {/snippet}

  {#snippet toolbar()}
    <div class="school-toolbar">
      <label for="school-select">表示する園</label>
      <select
        id="school-select"
        value={shell.schools.schoolId ?? ''}
        onchange={(event) => shell.selectSchool(event.currentTarget.value)}
        disabled={shell.schools.schools.length < 2}
      >
        {#each shell.schools.schools as school (school.id)}
          <option value={school.id}>{school.name}</option>
        {/each}
      </select>
      {#if shell.teacher}
        <span>{shell.teacher.name} さん</span>
      {:else}
        <span>開発モード（先生管理者）</span>
      {/if}
    </div>
  {/snippet}

  <AppShell
    {title}
    eyebrow="Small Step"
    description={shell.schools.selectedSchool?.name ??
      '園がまだ登録されていません。'}
    {navItems}
    {currentPath}
    {headerActions}
    {toolbar}
  >
    {#if redirectedFromAdmin}
      <Notice tone="warning" title="権限がありません">
        <p>先生管理者専用の画面からホームへ移動しました。</p>
      </Notice>
      {@render children()}
    {:else}
      {@render children()}
    {/if}
  </AppShell>
{/if}

<style>
  .startup-error {
    display: grid;
    width: min(100% - var(--ss-space-4), 48rem);
    min-height: 100vh;
    box-sizing: border-box;
    align-content: center;
    gap: var(--ss-space-2);
    margin-inline: auto;
  }

  .startup-error h1,
  .startup-error p {
    margin: 0;
  }

  .school-toolbar {
    display: flex;
    align-items: center;
    gap: var(--ss-space-2);
  }

  .school-toolbar label {
    font-weight: var(--ss-font-weight-bold);
  }

  .school-toolbar select {
    min-height: 44px;
    border: 2px solid var(--ss-color-border);
    border-radius: var(--ss-radius-medium);
    padding: var(--ss-space-1) var(--ss-space-2);
    background: var(--ss-color-surface);
    font: inherit;
  }

  .school-toolbar select:focus-visible {
    outline: 4px solid var(--ss-color-focus-inner);
    outline-offset: 0;
    box-shadow: 0 0 0 6px var(--ss-color-focus-outer);
  }

  @media (max-width: 47.999rem) {
    .school-toolbar {
      align-items: stretch;
      flex-direction: column;
    }
  }
</style>
