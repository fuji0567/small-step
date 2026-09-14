<script lang="ts">
  import type { ApiClient } from '$lib/api';
  import {
    Button,
    ConfirmDialog,
    Loading,
    Notice,
    StatusBadge
  } from '$lib/components';
  import type { AppController } from '$lib/state';
  import { onMount } from 'svelte';

  import { VoiceConsentService } from './service';
  import type {
    VoiceConsent,
    Voiceprint,
    VoiceprintJob,
    VoiceprintJobKind
  } from './types';
  import './voice-consent.css';

  type Props = {
    api: ApiClient;
    enabled: boolean;
    voiceprintEnabled: boolean;
    controller: AppController;
  };

  let { api, enabled, voiceprintEnabled, controller }: Props = $props();
  const service = $derived(new VoiceConsentService(api));
  let consent = $state<VoiceConsent | null>(null);
  let voiceprint = $state<Voiceprint | null>(null);
  let activeJob = $state<VoiceprintJob | null>(null);
  let audioFile = $state<File | null>(null);
  let retentionDays = $state(30);
  let accepted = $state(false);
  let loading = $state(false);
  let busy = $state(false);
  let errorMessage = $state<string | null>(null);
  let noticeMessage = $state<string | null>(null);
  let revokeOpen = $state(false);
  let deleteOpen = $state(false);

  function formatDateTime(value: string): string {
    return new Intl.DateTimeFormat('ja-JP', {
      dateStyle: 'long',
      timeStyle: 'short'
    }).format(new Date(value));
  }

  async function load(signal?: AbortSignal): Promise<void> {
    if (!enabled) {
      consent = null;
      return;
    }
    loading = true;
    errorMessage = null;
    try {
      [consent, voiceprint] = await Promise.all([
        service.get(signal),
        service.getVoiceprint(signal)
      ]);
      if (consent) retentionDays = consent.retention_days;
    } catch (error) {
      if (signal?.aborted) return;
      errorMessage =
        error instanceof Error
          ? error.message
          : '声紋設定を取得できませんでした。';
    } finally {
      loading = false;
    }
  }

  async function grant(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    if (!accepted) {
      errorMessage = '説明を確認し、同意する場合はチェックを入れてください。';
      return;
    }
    if (
      !Number.isInteger(retentionDays) ||
      retentionDays < 1 ||
      retentionDays > 365
    ) {
      errorMessage = '同意の有効期間は1日から365日の範囲で入力してください。';
      return;
    }
    busy = true;
    errorMessage = null;
    try {
      consent = await service.grant(retentionDays);
      accepted = false;
      noticeMessage =
        '声紋登録への同意を保存しました。声紋や音声はまだ登録されていません。';
      await controller.refresh(['voiceConsent']);
    } catch (error) {
      errorMessage =
        error instanceof Error ? error.message : '同意を保存できませんでした。';
    } finally {
      busy = false;
    }
  }

  async function revoke(): Promise<void> {
    if (!consent?.is_active) return;
    busy = true;
    errorMessage = null;
    try {
      consent = await service.revoke();
      voiceprint = null;
      activeJob = null;
      noticeMessage =
        '同意を取り消し、登録済みの声紋と処理中の音声を削除しました。';
      await controller.refresh(['voiceConsent']);
    } catch (error) {
      errorMessage =
        error instanceof Error ? error.message : '同意を取り消せませんでした。';
    } finally {
      busy = false;
    }
  }

  function chooseAudio(event: Event): void {
    const input = event.currentTarget as HTMLInputElement;
    audioFile = input.files?.[0] ?? null;
  }

  async function waitForJob(job: VoiceprintJob): Promise<void> {
    let current = job;
    activeJob = current;
    for (let attempt = 0; attempt < 60; attempt += 1) {
      if (!['queued', 'processing'].includes(current.status)) return;
      await new Promise((resolve) => globalThis.setTimeout(resolve, 1000));
      const next = await service.getJob(job.id);
      if (!next) throw new Error('声紋処理の状態を確認できませんでした。');
      current = next;
      activeJob = current;
    }
    throw new Error('声紋処理が時間内に完了しませんでした。');
  }

  async function submitVoiceprint(kind: VoiceprintJobKind): Promise<void> {
    if (!audioFile) {
      errorMessage = '先生本人が話している短い音声ファイルを選択してください。';
      return;
    }
    busy = true;
    errorMessage = null;
    noticeMessage = null;
    try {
      const job =
        kind === 'enrollment'
          ? await service.enroll(audioFile)
          : await service.verify(audioFile);
      if (!job) throw new Error('声紋処理を開始できませんでした。');
      await waitForJob(job);
      if (activeJob?.status === 'failed' || activeJob?.status === 'expired') {
        throw new Error(
          '音声を処理できませんでした。雑音の少ない音声でやり直してください。'
        );
      }
      if (kind === 'enrollment') {
        voiceprint = await service.getVoiceprint();
        noticeMessage = '声紋を暗号化して登録しました。元の音声は削除済みです。';
      } else {
        noticeMessage = activeJob?.matched
          ? '本人の声と一致しました。'
          : '本人の声と一致しませんでした。別の音声で再確認してください。';
      }
      audioFile = null;
    } catch (error) {
      errorMessage =
        error instanceof Error ? error.message : '声紋処理を完了できませんでした。';
    } finally {
      busy = false;
    }
  }

  async function deleteVoiceprint(): Promise<void> {
    busy = true;
    errorMessage = null;
    try {
      await service.deleteVoiceprint();
      voiceprint = null;
      activeJob = null;
      noticeMessage = '登録済みの声紋を削除しました。';
    } catch (error) {
      errorMessage =
        error instanceof Error ? error.message : '声紋を削除できませんでした。';
    } finally {
      busy = false;
    }
  }

  onMount(() => controller.register('voiceConsent', () => load()));

  $effect(() => {
    if (!enabled) return;
    const abort = new AbortController();
    void load(abort.signal);
    return () => abort.abort();
  });
</script>

<section class="voice-page" aria-labelledby="voice-heading">
  <header class="voice-heading">
    <h2 id="voice-heading">声紋設定</h2>
    <p>園内の話者識別に使う声紋登録への同意を管理します。</p>
  </header>

  {#if !enabled}
    <Notice tone="info" title="開発モードでは変更できません">
      <p>
        声紋設定は、Supabaseでログインした先生アカウントでのみ変更できます。
      </p>
    </Notice>
  {:else}
    {#if loading}<Loading label="声紋設定を読み込んでいます" />{/if}
    {#if noticeMessage}<Notice tone="success"><p>{noticeMessage}</p></Notice
      >{/if}
    {#if errorMessage}
      <Notice tone="error" title="声紋設定を処理できませんでした"
        ><p>{errorMessage}</p></Notice
      >
    {/if}
    {#if !voiceprintEnabled}
      <Notice tone="info" title="声紋の登録・本人確認は現在停止中です">
        <p>
          新しい登録と本人確認はできませんが、保存済み声紋の削除や同意の取消はいつでも行えます。
        </p>
      </Notice>
    {/if}

    <div class="voice-panel">
      {#if consent?.is_active}
        <StatusBadge label="同意済み" tone="success" />
        <p>有効期限: {formatDateTime(consent.expires_at)}</p>
      {:else if consent?.revoked_at}
        <StatusBadge label="同意取消済み" tone="warning" />
        <p>再開するには、説明を確認してもう一度同意を保存してください。</p>
      {:else if consent}
        <StatusBadge label="有効期限切れ" tone="warning" />
        <p>再開するには、説明を確認してもう一度同意を保存してください。</p>
      {:else}
        <StatusBadge label="未同意" tone="neutral" />
        <p>声紋登録への同意はまだ保存されていません。</p>
      {/if}

      <form class="voice-form" onsubmit={grant}>
        <div class="voice-field">
          <label for="retention-days">同意の有効期間（日）</label>
          <input
            id="retention-days"
            type="number"
            min="1"
            max="365"
            step="1"
            required
            bind:value={retentionDays}
          />
        </div>
        <label class="voice-confirmation">
          <input type="checkbox" bind:checked={accepted} />
          <span>園内での話者識別のため、声紋を登録することに同意します。</span>
          <span></span>
          <small
            >この操作だけでは声紋や音声は登録されません。同意はいつでも取り消せます。</small
          >
        </label>
        <div class="voice-actions">
          <Button type="submit" loading={busy}
            >{consent ? '同意を更新' : '同意を保存'}</Button
          >
          {#if consent?.is_active}
            <Button
              variant="danger"
              onclick={() => (revokeOpen = true)}
              guide="同意を取り消し、登録済み声紋と処理中の音声を削除します。"
              disabled={busy}>同意を取り消す</Button
            >
          {/if}
        </div>
      </form>

      {#if consent?.is_active}
        <section class="voice-enrollment" aria-labelledby="voice-enrollment-heading">
          <div class="voice-enrollment__heading">
            <div>
              <h3 id="voice-enrollment-heading">声紋の登録・本人確認</h3>
              <p>雑音が少なく、先生本人だけが5〜15秒ほど話している音声を使います。</p>
            </div>
            {#if voiceprint}
              <StatusBadge label="登録済み" tone="success" />
            {:else}
              <StatusBadge label="未登録" tone="neutral" />
            {/if}
          </div>

          {#if voiceprint}
            <p>登録日時: {formatDateTime(voiceprint.enrolled_at)}</p>
            <p>保存期限: {formatDateTime(voiceprint.expires_at)}</p>
          {/if}

          {#if voiceprintEnabled}
            <label class="voice-file">
              <span>先生本人の音声ファイル</span>
              <input type="file" accept="audio/*" onchange={chooseAudio} disabled={busy} />
              <small
                >選択した音声は処理完了・失敗・期限切れの時点でサーバーから削除されます。</small
              >
            </label>

            <div class="voice-actions">
              <Button
                onclick={() => submitVoiceprint('enrollment')}
                loading={busy}
                disabled={!audioFile}>声紋を{voiceprint ? '再登録' : '登録'}</Button
              >
              {#if voiceprint}
                <Button
                  variant="secondary"
                  onclick={() => submitVoiceprint('verification')}
                  disabled={busy || !audioFile}>本人確認を試す</Button
                >
              {/if}
            </div>
          {/if}

          {#if voiceprint}
            <div class="voice-actions">
              <Button
                variant="danger"
                onclick={() => (deleteOpen = true)}
                disabled={busy}>声紋を削除</Button
              >
            </div>
          {/if}

          {#if activeJob?.status === 'queued' || activeJob?.status === 'processing'}
            <Notice tone="info"><p>GPUで声の特徴を処理しています。</p></Notice>
          {:else if activeJob?.kind === 'verification' && activeJob.status === 'completed'}
            <StatusBadge
              label={activeJob.matched ? '本人一致' : '不一致'}
              tone={activeJob.matched ? 'success' : 'warning'}
            />
          {/if}
        </section>
      {/if}
    </div>
  {/if}
</section>

<ConfirmDialog
  bind:open={revokeOpen}
  title="声紋登録への同意を取り消しますか？"
  description="以後の声紋登録を停止し、登録済み声紋と処理中の音声をすべて削除します。"
  confirmLabel="同意を取り消す"
  tone="danger"
  {busy}
  onConfirm={revoke}
/>

<ConfirmDialog
  bind:open={deleteOpen}
  title="登録済みの声紋を削除しますか？"
  description="暗号化済みの特徴量と処理履歴を削除します。同意は残るため、必要になったら再登録できます。"
  confirmLabel="声紋を削除"
  tone="danger"
  {busy}
  onConfirm={deleteVoiceprint}
/>
