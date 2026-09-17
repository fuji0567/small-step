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
  let trialConfirmOpen = $state(false);
  let deliveryConfirmed = $state(false);
  let modeSchoolId = '';
  let nextTrialMode = $state(true);
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

  function requestModeChange(): void {
    if (!school || busy || (school.trial_mode && !deliveryConfirmed)) return;
    modeSchoolId = school.id;
    nextTrialMode = !school.trial_mode;
    trialConfirmOpen = true;
  }

  async function saveMode(): Promise<void> {
    if (!school || school.id !== modeSchoolId || busy) return;
    const id = modeSchoolId;
    busy = true;
    errorMessage = null;
    successMessage = null;
    try {
      await service.updateTrialMode(
        id,
        nextTrialMode,
        !nextTrialMode && deliveryConfirmed
      );
      await appController.refresh(['schools']);
      if (school?.id === id)
        successMessage =
          '利用モードを変更しました。試用記録は今後も配信されません。';
    } catch {
      if (school?.id === id)
        errorMessage =
          '利用モードを変更できませんでした。園の設定を再読み込みして確認してください。';
    } finally {
      busy = false;
      trialConfirmOpen = false;
      deliveryConfirmed = false;
    }
  }

  $effect(() => {
    digestTime = school?.digest_time ?? '17:00';
    confirmOpen = false;
    trialConfirmOpen = false;
    deliveryConfirmed = false;
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
    <div class="settings-card">
      <h3>利用モード</h3>
      <Notice
        tone={school.trial_mode ? 'warning' : 'info'}
        title={school.trial_mode
          ? '試用中（保護者への配信なし）'
          : '本番モード'}
      >
        <p>
          試用モードでは録音・候補作成・承認まで試せますが、保護者のLINEには送信しません。試用中の記録は、本番へ切り替えても配信されません。
        </p>
      </Notice>
      {#if school.trial_mode}
        <label
          ><input
            type="checkbox"
            bind:checked={deliveryConfirmed}
            disabled={busy}
          /> 本番への切り替え後、新しい記録は承認すると保護者へ配信されることを確認しました</label
        >
      {:else}
        <p>
          試用へ切り替えると、未承認の記録、処理中の録音、送信待ち・連携待ち・失敗通知も試用扱いになります。これらは再び本番へ切り替えても配信されません。すでに送信開始した通知は取り消せません。
        </p>
      {/if}
      <Button
        variant="secondary"
        onclick={requestModeChange}
        disabled={busy || (!!school.trial_mode && !deliveryConfirmed)}
      >
        {school.trial_mode ? '本番モードへ切り替え' : '試用モードへ切り替え'}
      </Button>
    </div>
    <form class="settings-card" onsubmit={requestSave}>
      <div class="settings-field">
        <label for="digest-time">成長記録の既定配信時刻</label>
        <input id="digest-time" type="time" required bind:value={digestTime} />
        <p>
          本番モードのけがの記録はこの設定にかかわらず、承認後すぐに配信対象になります。試用記録は配信されません。
        </p>
      </div>
      <Button type="submit" loading={busy}>配信時刻を保存</Button>
    </form>
  {/if}
</section>

<ConfirmDialog
  bind:open={trialConfirmOpen}
  title={nextTrialMode
    ? '試用モードへ切り替えますか？'
    : '保護者への配信を有効にしますか？'}
  description={nextTrialMode
    ? '未承認・処理中・送信待ち・連携待ち・失敗の記録も配信しない試用扱いになります。本番に戻してもこれらは配信されません。送信開始済みの通知は取り消せません。'
    : '切り替え後に作る新しい記録は、先生の承認後に保護者へ配信されます。既存の試用記録は送信されません。'}
  confirmLabel={nextTrialMode ? '試用に切り替える' : '配信を有効にする'}
  {busy}
  onConfirm={saveMode}
/>

<ConfirmDialog
  bind:open={confirmOpen}
  title="既定の配信時刻を変更しますか？"
  description={`${digestTime}を今後承認する成長記録の既定配信時刻にします。すでに送信待ちの通知時刻は変わりません。`}
  confirmLabel="配信時刻を保存"
  {busy}
  onConfirm={save}
/>
