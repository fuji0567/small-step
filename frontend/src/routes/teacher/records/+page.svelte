<script lang="ts">
  import { RecordHistoryView } from '$lib/features/records';
  import { useTeacherShell } from '$lib/features/teacher-shell';

  const shell = useTeacherShell();
</script>

<svelte:head>
  <title>記録履歴 | Small Step</title>
</svelte:head>

<RecordHistoryView
  api={shell.api}
  schoolId={shell.schools.schoolId}
  isSchoolAdmin={shell.isSchoolAdmin}
/>
