<script lang="ts">
  import { AppShell } from '$lib/components';
  import { teacherNavItems } from './navigation';

  let {
    isSchoolAdmin = false,
    classDeliveryEnabled = false,
    currentPath = '/teacher/'
  }: {
    isSchoolAdmin?: boolean;
    classDeliveryEnabled?: boolean;
    currentPath?: string;
  } = $props();
</script>

<AppShell
  title="テスト画面"
  navItems={teacherNavItems(isSchoolAdmin, undefined, classDeliveryEnabled)}
  {currentPath}
>
  <p>本文</p>
</AppShell>
