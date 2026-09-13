<script lang="ts">
  import {
    provideTeacherShell,
    TeacherShellState
  } from '$lib/features/teacher-shell';
  import TeacherPage from '../../../routes/teacher/+page.svelte';

  const shell = new TeacherShellState((input, init) =>
    globalThis.fetch(input, init)
  );
  provideTeacherShell(shell);
</script>

<TeacherPage />
