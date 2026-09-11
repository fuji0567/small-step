<script lang="ts">
  import type { ApiClient } from '$lib/api';
  import { Button, ConfirmDialog, Notice } from '$lib/components';
  import type { AppController, SchoolSummary } from '$lib/state';

  import { SchoolSettingsService } from './settings-service';
  import './settings.css';

  type Props = {
    api: ApiClient;
    appController: AppController;
    school: SchoolSummary | null;
    isSchoolAdmin: boolean;
    onReloadSchools: () => void | Promise<void>;
  };

  let { api, appController, school, isSchoolAdmin, onReloadSchools }: Props =
    $props();
  const service = $derived(new SchoolSettingsService(api));
  let digestTime = $state('17:00');
  let confirmOpen = $state(false);
  let busy = $state(false);
  let errorMessage = $state<string | null>(null);
  let successMessage = $state<string | null>(null);

  function requestSave(event: SubmitEvent): void {
    event.preventDefault();
    if (!/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(digestTime)) {
      errorMessage = '配信時刻を時:分の形式で入力してください。';
      return;
    }
    confirmOpen = true;
  }

  async function save(): Promise<void> {
    if (!school || busy) return;
    busy = true;
    errorMessage = null;
    try {
      await service.updateDigestTime(school.id, digestTime);
      await appController.refresh(['schools']);
      successMessage = `成長記録の既定配信時刻を${digestTime}に変更しました。`;
    } catch {
      errorMessage = '既定の配信時刻を変更できませんでした。';
    } finally {
      busy = false;
      confirmOpen = false;
    }
  }

  $effect(() => {
    digestTime = school?.digest_time ?? '17:00';
    confirmOpen = false;
    errorMessage = null;
    successMessage = null;
  });

  $effect(() => {
    const unregister = appController.register('schools', onReloadSchools);
    return unregister;
  });
</script>

<section class="settings-page" aria-labelledby="settings-heading">
  <header>
    <h2 id="settings-heading">園の設定</h2>
    <p>今後承認する成長記録の既定配信時刻を設定します。</p>
  </header>

  {#if !isSchoolAdmin}
    <Notice tone="warning" title="先生管理者専用です"
      ><p>この画面を利用する権限がありません。</p></Notice
    >
  {:else if !school}
    <Notice tone="warning" title="園を選択してください"
      ><p>園を選択すると設定を変更できます。</p></Notice
    >
  {:else}
    {#if successMessage}<Notice tone="success"><p>{successMessage}</p></Notice
      >{/if}
    {#if errorMessage}<Notice tone="error" title="設定を変更できませんでした"
        ><p>{errorMessage}</p></Notice
      >{/if}
    <form class="settings-card" onsubmit={requestSave}>
      <div class="settings-field">
        <label for="digest-time">成長記録の既定配信時刻</label>
        <input id="digest-time" type="time" required bind:value={digestTime} />
        <p>
          けがの記録はこの設定にかかわらず、承認後すぐに配信対象になります。
        </p>
      </div>
      <Button type="submit" loading={busy}>配信時刻を保存</Button>
    </form>
  {/if}
</section>

<ConfirmDialog
  bind:open={confirmOpen}
  title="既定の配信時刻を変更しますか？"
  description={`${digestTime}を今後承認する成長記録の既定配信時刻にします。すでに送信待ちの通知時刻は変わりません。`}
  confirmLabel="配信時刻を保存"
  {busy}
  onConfirm={save}
/>
