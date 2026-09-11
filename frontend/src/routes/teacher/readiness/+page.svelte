<script lang="ts">
  import { ReadinessView } from '$lib/features/operations';
  import { useTeacherShell } from '$lib/features/teacher-shell';

  const shell = useTeacherShell();
</script>

<svelte:head><title>稼働準備チェック | Small Step</title></svelte:head>
<ReadinessView
  api={shell.api}
  isSchoolAdmin={shell.isSchoolAdmin}
  controller={shell.controller}
/>
