<script lang="ts">
  import { goto } from '$app/navigation';
  import { resolve } from '$app/paths';
  import { page } from '$app/state';
  import { RecordDetailView } from '$lib/features/records';
  import { useTeacherShell } from '$lib/features/teacher-shell';

  const shell = useTeacherShell();
  const recordId = $derived(page.params.recordId ?? '');
</script>

<svelte:head>
  <title>日誌のレビュー | Small Step</title>
</svelte:head>

<RecordDetailView
  api={shell.api}
  schoolId={shell.schools.schoolId}
  {recordId}
  isSchoolAdmin={shell.isSchoolAdmin}
  onNavigate={(path) => goto(resolve(path))}
  onReassigned={() =>
    shell.refresh(['records', 'recordHistory', 'auditEvents'])}
/>
