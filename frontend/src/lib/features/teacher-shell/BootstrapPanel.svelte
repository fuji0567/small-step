<script lang="ts">
  import { Button, Notice } from '$lib/components';
  import type { TeacherShellState } from './teacher-shell.svelte';

  let { shell }: { shell: TeacherShellState } = $props();
  let schoolId = $state('');
  let name = $state('');
  let submitting = $state(false);

  $effect(() => {
    if (schoolId === '') schoolId = shell.bootstrapSchools[0]?.id ?? '';
  });

  async function submit(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    submitting = true;
    try {
      await shell.completeBootstrap(schoolId, name.trim());
    } finally {
      submitting = false;
    }
  }
</script>

<main class="auth-panel">
  <section aria-labelledby="bootstrap-heading">
    <p class="eyebrow">Small Step</p>
    <h1 id="bootstrap-heading">初回設定</h1>
    <p>管理する園と、画面に表示する先生名を登録してください。</p>

    {#if shell.errorMessage}
      <Notice tone="error" title="登録できませんでした">
        <p>{shell.errorMessage}</p>
      </Notice>
    {/if}

    <form onsubmit={submit}>
      <label for="bootstrap-school">管理する園</label>
      <select id="bootstrap-school" required bind:value={schoolId}>
        {#each shell.bootstrapSchools as school (school.id)}
          <option value={school.id}>{school.name}</option>
        {/each}
      </select>
      <label for="bootstrap-name">先生名</label>
      <input
        id="bootstrap-name"
        name="name"
        autocomplete="name"
        maxlength="120"
        required
        bind:value={name}
      />
      <Button type="submit" loading={submitting}>管理者として登録</Button>
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

  section,
  form {
    display: grid;
    gap: var(--ss-space-2);
  }

  section {
    width: min(100%, 32rem);
    box-sizing: border-box;
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

  input,
  select {
    min-height: 44px;
    box-sizing: border-box;
    border: 2px solid var(--ss-color-border);
    border-radius: var(--ss-radius-medium);
    padding: var(--ss-space-1) var(--ss-space-2);
    background: var(--ss-color-surface);
    font: inherit;
  }

  input:focus-visible,
  select:focus-visible {
    outline: 4px solid var(--ss-color-focus-inner);
    outline-offset: 0;
    box-shadow: 0 0 0 6px var(--ss-color-focus-outer);
  }
</style>
