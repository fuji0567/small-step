<script lang="ts">
  import { ReviewQueueView } from '$lib/features/records';
  import { useTeacherShell } from '$lib/features/teacher-shell';

  const shell = useTeacherShell();
</script>

<svelte:head>
  <title>レビュー待ち日誌 | Small Step</title>
</svelte:head>

<ReviewQueueView
  api={shell.api}
  schoolId={shell.schools.schoolId}
  isSchoolAdmin={shell.isSchoolAdmin}
/>
