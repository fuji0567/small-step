<script lang="ts">
  import { DevicesView } from '$lib/features/devices';
  import { useTeacherShell } from '$lib/features/teacher-shell';

  const shell = useTeacherShell();
</script>

<svelte:head><title>録音端末 | Small Step</title></svelte:head>
<DevicesView
  api={shell.api}
  appController={shell.controller}
  schoolId={shell.schools.schoolId}
  isSchoolAdmin={shell.isSchoolAdmin}
/>
