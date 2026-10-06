<script lang="ts">
  import { useTeacherShell } from '$lib/features/teacher-shell';
  import { ClassDeliveryView } from '$lib/features/class-delivery';

  const shell = useTeacherShell();
</script>

<svelte:head><title>今日の配信 | Small Step</title></svelte:head>
{#if shell.classDeliveryEnabled}
  <ClassDeliveryView
    api={shell.api}
    schoolId={shell.schools.schoolId}
    schoolTimezone={shell.schools.selectedSchool?.timezone ?? 'Asia/Tokyo'}
    schoolTrialMode={shell.schools.selectedSchool?.trial_mode === true}
    isSchoolAdmin={shell.isSchoolAdmin}
  />
{/if}
