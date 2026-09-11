<script lang="ts">
  import { NotificationsView } from '$lib/features/notifications';
  import { useTeacherShell } from '$lib/features/teacher-shell';

  const shell = useTeacherShell();
</script>

<svelte:head><title>通知状況 | Small Step</title></svelte:head>
<NotificationsView
  api={shell.api}
  schoolId={shell.schools.schoolId}
  isSchoolAdmin={shell.isSchoolAdmin}
  controller={shell.controller}
/>
