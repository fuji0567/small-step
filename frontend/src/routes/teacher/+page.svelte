<script lang="ts">
  import { DashboardView } from '$lib/features/dashboard';
  import { useTeacherShell } from '$lib/features/teacher-shell';

  const shell = useTeacherShell();
</script>

<svelte:head>
  <title>ホーム | Small Step</title>
</svelte:head>

<DashboardView
  api={shell.api}
  schoolId={shell.schools.schoolId}
  isSchoolAdmin={shell.isSchoolAdmin}
  controller={shell.controller}
/>
