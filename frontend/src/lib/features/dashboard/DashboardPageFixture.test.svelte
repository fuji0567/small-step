<script lang="ts">
  import {
    provideTeacherShell,
    TeacherShellState
  } from '$lib/features/teacher-shell';
  import TeacherPage from '../../../routes/teacher-next/+page.svelte';

  const shell = new TeacherShellState((input, init) =>
    globalThis.fetch(input, init)
  );
  provideTeacherShell(shell);
</script>

<TeacherPage />
