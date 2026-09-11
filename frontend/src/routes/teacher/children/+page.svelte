<script lang="ts">
  import { ChildrenView } from '$lib/features/children';
  import { useTeacherShell } from '$lib/features/teacher-shell';

  const shell = useTeacherShell();
</script>

<svelte:head><title>園児・保護者 | Small Step</title></svelte:head>
<ChildrenView
  api={shell.api}
  appController={shell.controller}
  schoolId={shell.schools.schoolId}
  isSchoolAdmin={shell.isSchoolAdmin}
/>
