<script lang="ts">
  import { goto } from '$app/navigation';
  import { resolve } from '$app/paths';
  import { ManualRecordView } from '$lib/features/records';
  import { useTeacherShell } from '$lib/features/teacher-shell';

  const shell = useTeacherShell();
</script>

<svelte:head>
  <title>日誌を手入力 | Small Step</title>
</svelte:head>

<ManualRecordView
  api={shell.api}
  schoolId={shell.schools.schoolId}
  currentTeacherId={shell.teacher?.id ?? null}
  onNavigate={(path) => goto(resolve(path))}
/>
