<script lang="ts">
  import { useTeacherShell } from '$lib/features/teacher-shell';
  import { VoiceConsentView } from '$lib/features/voice-consent';

  const shell = useTeacherShell();
</script>

<svelte:head><title>声紋設定 | Small Step</title></svelte:head>
<VoiceConsentView
  api={shell.api}
  enabled={shell.canLogout}
  voiceprintEnabled={shell.voiceprintEnabled}
  controller={shell.controller}
/>
