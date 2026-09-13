<script lang="ts">
  import { AudioJobsView } from '$lib/features/operations';
  import { useTeacherShell } from '$lib/features/teacher-shell';

  const shell = useTeacherShell();
</script>

<svelte:head><title>音声処理状況 | Small Step</title></svelte:head>
<AudioJobsView
  api={shell.api}
  schoolId={shell.schools.schoolId}
  controller={shell.controller}
/>
