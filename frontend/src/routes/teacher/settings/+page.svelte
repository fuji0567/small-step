<script lang="ts">
  import { useTeacherShell } from '$lib/features/teacher-shell';
  import { SchoolSettingsView } from '$lib/features/teachers';

  const shell = useTeacherShell();
</script>

<svelte:head><title>園の設定 | Small Step</title></svelte:head>
<SchoolSettingsView
  api={shell.api}
  appController={shell.controller}
  school={shell.schools.selectedSchool}
  isSchoolAdmin={shell.isSchoolAdmin}
  onReloadSchools={() => shell.reloadSchools()}
/>
