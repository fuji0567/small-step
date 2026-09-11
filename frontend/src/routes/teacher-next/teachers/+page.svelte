<script lang="ts">
  import { useTeacherShell } from '$lib/features/teacher-shell';
  import { TeachersView } from '$lib/features/teachers';

  const shell = useTeacherShell();
</script>

<svelte:head><title>先生管理 | Small Step</title></svelte:head>
<TeachersView
  api={shell.api}
  appController={shell.controller}
  schoolId={shell.schools.schoolId}
  isSchoolAdmin={shell.isSchoolAdmin}
  currentTeacherId={shell.teacher?.id ?? null}
/>
