<script lang="ts">
  import { AuditEventsView } from '$lib/features/operations';
  import { useTeacherShell } from '$lib/features/teacher-shell';

  const shell = useTeacherShell();
</script>

<svelte:head><title>操作履歴 | Small Step</title></svelte:head>
<AuditEventsView
  api={shell.api}
  schoolId={shell.schools.schoolId}
  isSchoolAdmin={shell.isSchoolAdmin}
  controller={shell.controller}
/>
