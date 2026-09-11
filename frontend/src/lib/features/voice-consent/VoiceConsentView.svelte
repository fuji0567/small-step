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
  import type { VoiceConsent } from './types';
  import './voice-consent.css';

  type Props = {
    api: ApiClient;
    enabled: boolean;
    controller: AppController;
  };

  let { api, enabled, controller }: Props = $props();
  const service = $derived(new VoiceConsentService(api));
  let consent = $state<VoiceConsent | null>(null);
  let retentionDays = $state(30);
  let accepted = $state(false);
  let loading = $state(false);
  let busy = $state(false);
  let errorMessage = $state<string | null>(null);
  let noticeMessage = $state<string | null>(null);
  let revokeOpen = $state(false);

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
      consent = await service.get(signal);
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
      noticeMessage =
        '声紋登録への同意を取り消しました。以後の声紋登録は開始されません。';
      await controller.refresh(['voiceConsent']);
    } catch (error) {
      errorMessage =
        error instanceof Error ? error.message : '同意を取り消せませんでした。';
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
              disabled={busy}>同意を取り消す</Button
            >
          {/if}
        </div>
      </form>
    </div>
  {/if}
</section>

<ConfirmDialog
  bind:open={revokeOpen}
  title="声紋登録への同意を取り消しますか？"
  description="以後の声紋登録は開始できなくなります。この操作だけで既存の声紋データが削除されるわけではありません。"
  confirmLabel="同意を取り消す"
  tone="danger"
  {busy}
  onConfirm={revoke}
/>
