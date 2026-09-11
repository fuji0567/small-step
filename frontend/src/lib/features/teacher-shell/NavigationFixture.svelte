<script lang="ts">
  import { AppShell } from '$lib/components';
  import { teacherNavItems } from './navigation';

  let {
    isSchoolAdmin = false,
    currentPath = '/teacher/'
  }: {
    isSchoolAdmin?: boolean;
    currentPath?: string;
  } = $props();
</script>

<AppShell
  title="テスト画面"
  navItems={teacherNavItems(isSchoolAdmin)}
  {currentPath}
>
  <p>本文</p>
</AppShell>
