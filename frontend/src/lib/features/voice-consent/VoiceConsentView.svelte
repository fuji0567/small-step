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
    VoiceprintJobKind,
    VoiceprintQualityIssue
  } from './types';
  import {
    createVoiceRecordingFile,
    MAX_VOICE_RECORDING_SECONDS,
    MIN_VOICE_RECORDING_SECONDS,
    selectVoiceRecordingFormat,
    VOICEPRINT_ENROLLMENT_SAMPLE_COUNT,
    type VoiceRecordingFormat
  } from './voice-recorder';
  import './voice-consent.css';

  type Props = {
    api: ApiClient;
    enabled: boolean;
    voiceprintEnabled: boolean;
    controller: AppController;
  };

  type CapturedSample = {
    file: File;
    previewUrl: string;
    durationSeconds: number | null;
  };

  let { api, enabled, voiceprintEnabled, controller }: Props = $props();
  const service = $derived(new VoiceConsentService(api));
  let consent = $state<VoiceConsent | null>(null);
  let voiceprint = $state<Voiceprint | null>(null);
  let activeJob = $state<VoiceprintJob | null>(null);
  let captureKind = $state<VoiceprintJobKind>('enrollment');
  let capturedSamples = $state<CapturedSample[]>([]);
  const requiredSampleCount = $derived(
    captureKind === 'enrollment' ? VOICEPRINT_ENROLLMENT_SAMPLE_COUNT : 1
  );
  let recordingSupported = $state(false);
  let recordingStarting = $state(false);
  let recording = $state(false);
  let recordingSeconds = $state(0);
  let retentionDays = $state(30);
  let accepted = $state(false);
  let loading = $state(false);
  let busy = $state(false);
  let errorMessage = $state<string | null>(null);
  let noticeMessage = $state<string | null>(null);
  let revokeOpen = $state(false);
  let deleteOpen = $state(false);
  let mediaRecorder: MediaRecorder | null = null;
  let mediaStream: MediaStream | null = null;
  let recordingStartedAt = 0;
  let recordingRequestId = 0;
  let recordingTimer: ReturnType<typeof globalThis.setInterval> | null = null;

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
      cleanupActiveRecording();
      clearCapturedSamples();
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

  function stopRecordingTimer(): void {
    if (recordingTimer === null) return;
    globalThis.clearInterval(recordingTimer);
    recordingTimer = null;
  }

  function stopMediaStream(): void {
    mediaStream?.getTracks().forEach((track) => track.stop());
    mediaStream = null;
  }

  function clearCapturedSamples(): void {
    for (const sample of capturedSamples) {
      URL.revokeObjectURL(sample.previewUrl);
    }
    capturedSamples = [];
    recordingSeconds = 0;
  }

  function removeCapturedSample(index: number, announce = true): void {
    const sample = capturedSamples[index];
    if (!sample) return;
    URL.revokeObjectURL(sample.previewUrl);
    capturedSamples = capturedSamples.filter(
      (_capturedSample, sampleIndex) => sampleIndex !== index
    );
    activeJob = null;
    if (announce) {
      noticeMessage = `${index + 1}回目の音声を外しました。もう一度録音してください。`;
    }
  }

  function selectCaptureKind(kind: VoiceprintJobKind): void {
    if (captureKind === kind) return;
    cleanupActiveRecording();
    clearCapturedSamples();
    captureKind = kind;
    activeJob = null;
    errorMessage = null;
    noticeMessage = null;
  }

  function cleanupActiveRecording(): void {
    recordingRequestId += 1;
    stopRecordingTimer();
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.onstop = null;
      mediaRecorder.onerror = null;
      mediaRecorder.ondataavailable = null;
      mediaRecorder.stop();
    }
    mediaRecorder = null;
    stopMediaStream();
    recordingStarting = false;
    recording = false;
  }

  function completeRecording(
    chunks: Blob[],
    format: VoiceRecordingFormat,
    durationSeconds: number
  ): void {
    stopRecordingTimer();
    stopMediaStream();
    mediaRecorder = null;
    recordingStarting = false;
    recording = false;
    recordingSeconds = Math.min(
      MAX_VOICE_RECORDING_SECONDS,
      Math.max(0, Math.round(durationSeconds))
    );

    if (durationSeconds < MIN_VOICE_RECORDING_SECONDS) {
      errorMessage = `録音が短すぎます。${MIN_VOICE_RECORDING_SECONDS}秒以上話してから停止してください。`;
      return;
    }
    if (!chunks.some((chunk) => chunk.size > 0)) {
      errorMessage = '音声を録音できませんでした。マイクを確認してください。';
      return;
    }

    try {
      const file = createVoiceRecordingFile(chunks, format.mimeType);
      capturedSamples = [
        ...capturedSamples,
        {
          file,
          previewUrl: URL.createObjectURL(file),
          durationSeconds: Math.min(
            MAX_VOICE_RECORDING_SECONDS,
            Math.round(durationSeconds)
          )
        }
      ];
      recordingSeconds = Math.min(
        MAX_VOICE_RECORDING_SECONDS,
        Math.round(durationSeconds)
      );
      noticeMessage =
        capturedSamples.length === requiredSampleCount
          ? `${capturedSamples.length}/${requiredSampleCount}回の録音が完了しました。内容を確認して送信してください。`
          : `${capturedSamples.length}/${requiredSampleCount}回完了しました。次の音声を録音してください。`;
    } catch (error) {
      errorMessage =
        error instanceof Error ? error.message : '録音を保存できませんでした。';
    }
  }

  async function startRecording(): Promise<void> {
    if (recordingStarting || recording) return;
    if (capturedSamples.length >= requiredSampleCount) {
      errorMessage =
        '必要な回数の録音が完了しています。録り直す音声を外してください。';
      return;
    }
    errorMessage = null;
    noticeMessage = null;
    const format = selectVoiceRecordingFormat((mimeType) =>
      MediaRecorder.isTypeSupported(mimeType)
    );
    if (!format) {
      errorMessage =
        'このブラウザの録音形式には対応していません。音声ファイルを選択してください。';
      return;
    }

    cleanupActiveRecording();
    const requestId = ++recordingRequestId;
    recordingStarting = true;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      });
      if (requestId !== recordingRequestId) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      mediaStream = stream;
      const recorder = new MediaRecorder(stream, { mimeType: format.mimeType });
      const chunks: Blob[] = [];
      mediaRecorder = recorder;
      recordingStartedAt = Date.now();
      recordingSeconds = 0;

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunks.push(event.data);
      };
      recorder.onstop = () => {
        completeRecording(
          chunks,
          format,
          (Date.now() - recordingStartedAt) / 1000
        );
      };
      recorder.onerror = () => {
        recorder.onstop = null;
        cleanupActiveRecording();
        errorMessage = '録音中にエラーが発生しました。もう一度お試しください。';
      };

      recorder.start(250);
      recordingStarting = false;
      recording = true;
      recordingTimer = globalThis.setInterval(() => {
        const elapsed = (Date.now() - recordingStartedAt) / 1000;
        recordingSeconds = Math.min(
          MAX_VOICE_RECORDING_SECONDS,
          Math.floor(elapsed)
        );
        if (elapsed >= MAX_VOICE_RECORDING_SECONDS) stopRecording();
      }, 250);
    } catch (error) {
      if (requestId !== recordingRequestId) return;
      cleanupActiveRecording();
      errorMessage =
        error instanceof DOMException && error.name === 'NotAllowedError'
          ? 'マイクの使用が許可されていません。ブラウザの設定から許可してください。'
          : 'マイクを開始できませんでした。接続とブラウザ設定を確認してください。';
    }
  }

  function stopRecording(): void {
    const recorder = mediaRecorder;
    if (!recorder || recorder.state === 'inactive') return;
    stopRecordingTimer();
    recording = false;
    recordingSeconds = Math.min(
      MAX_VOICE_RECORDING_SECONDS,
      Math.floor((Date.now() - recordingStartedAt) / 1000)
    );
    recorder.stop();
  }

  function chooseAudio(event: Event): void {
    const input = event.currentTarget as HTMLInputElement;
    cleanupActiveRecording();
    const files = Array.from(input.files ?? []);
    if (files.length !== requiredSampleCount) {
      errorMessage = `${requiredSampleCount}件の音声ファイルを選択してください。`;
      input.value = '';
      return;
    }
    clearCapturedSamples();
    capturedSamples = files.map((file) => ({
      file,
      previewUrl: URL.createObjectURL(file),
      durationSeconds: null
    }));
    errorMessage = null;
    noticeMessage = `${files.length}/${requiredSampleCount}件の音声ファイルを選択しました。`;
    input.value = '';
  }

  const qualityIssueMessages: Record<VoiceprintQualityIssue, string> = {
    too_short:
      '話している時間が短すぎます。10秒以上、間を空けずに話してください。',
    too_long: '録音が長すぎます。10〜15秒に収めてください。',
    too_quiet: '声が小さすぎます。マイクに少し近づいて話してください。',
    too_noisy: '周囲の雑音が多すぎます。静かな場所で録音してください。',
    clipping: '音が割れています。マイクから少し離れて話してください。',
    multiple_speakers:
      '複数人の声が入っています。先生本人だけで録音してください。',
    invalid_audio: '音声を読み取れませんでした。もう一度録音してください。'
  };

  function qualityFailureMessage(job: VoiceprintJob): string {
    if (!job.quality_issue) {
      return '音声を処理できませんでした。雑音の少ない音声でやり直してください。';
    }
    const sampleLabel = job.quality_sample_index
      ? `${job.quality_sample_index}回目の音声: `
      : '';
    return `${sampleLabel}${qualityIssueMessages[job.quality_issue]}`;
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
    if (
      kind !== captureKind ||
      capturedSamples.length !== requiredSampleCount
    ) {
      errorMessage = `${requiredSampleCount}回分の先生本人の音声を用意してください。`;
      return;
    }
    busy = true;
    errorMessage = null;
    noticeMessage = null;
    try {
      let job: VoiceprintJob | null;
      if (kind === 'enrollment') {
        job = await service.enroll(
          capturedSamples.map((sample) => sample.file)
        );
      } else {
        const sample = capturedSamples[0];
        if (!sample) throw new Error('本人確認用の音声を用意してください。');
        job = await service.verify(sample.file);
      }
      if (!job) throw new Error('声紋処理を開始できませんでした。');
      await waitForJob(job);
      if (activeJob?.status === 'failed' || activeJob?.status === 'expired') {
        const failedJob = activeJob;
        const message = qualityFailureMessage(failedJob);
        if (failedJob.quality_sample_index) {
          removeCapturedSample(failedJob.quality_sample_index - 1, false);
        }
        throw new Error(message);
      }
      if (kind === 'enrollment') {
        voiceprint = await service.getVoiceprint();
        noticeMessage =
          '声紋を暗号化して登録しました。元の音声は削除済みです。';
      } else {
        noticeMessage = activeJob?.matched
          ? '本人の声と一致しました。'
          : '本人の声と一致しませんでした。別の音声で再確認してください。';
      }
      clearCapturedSamples();
    } catch (error) {
      errorMessage =
        error instanceof Error
          ? error.message
          : '声紋処理を完了できませんでした。';
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
      clearCapturedSamples();
      noticeMessage = '登録済みの声紋を削除しました。';
    } catch (error) {
      errorMessage =
        error instanceof Error ? error.message : '声紋を削除できませんでした。';
    } finally {
      busy = false;
    }
  }

  onMount(() => {
    recordingSupported =
      typeof MediaRecorder !== 'undefined' &&
      typeof navigator.mediaDevices?.getUserMedia === 'function';
    const unregister = controller.register('voiceConsent', () => load());
    return () => {
      unregister();
      cleanupActiveRecording();
      clearCapturedSamples();
    };
  });

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
        <section
          class="voice-enrollment"
          aria-labelledby="voice-enrollment-heading"
        >
          <div class="voice-enrollment__heading">
            <div>
              <h3 id="voice-enrollment-heading">声紋の登録・本人確認</h3>
              <p>
                雑音が少なく、先生本人だけが10〜15秒話している音声を使います。
              </p>
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
            <p>代表声紋: {voiceprint.sample_count}回の音声から作成</p>
          {/if}

          {#if voiceprintEnabled}
            {#if voiceprint}
              <div class="voice-mode" role="group" aria-label="声紋処理の種類">
                <Button
                  variant={captureKind === 'enrollment'
                    ? 'primary'
                    : 'secondary'}
                  aria-pressed={captureKind === 'enrollment'}
                  onclick={() => selectCaptureKind('enrollment')}
                  disabled={busy || recordingStarting || recording}
                  >3回録音して再登録</Button
                >
                <Button
                  variant={captureKind === 'verification'
                    ? 'primary'
                    : 'secondary'}
                  aria-pressed={captureKind === 'verification'}
                  onclick={() => selectCaptureKind('verification')}
                  disabled={busy || recordingStarting || recording}
                  >1回録音して本人確認</Button
                >
              </div>
            {/if}

            <div class="voice-recorder">
              <div class="voice-recorder__intro">
                <div>
                  <strong
                    >{captureKind === 'enrollment'
                      ? '代表声紋を作るための録音'
                      : '本人確認のための録音'}</strong
                  >
                  <p>
                    静かな場所で、普段の声量で10〜15秒話してください。15秒で自動停止します。
                  </p>
                </div>
                <strong class="voice-recorder__progress" aria-live="polite">
                  {capturedSamples.length}/{requiredSampleCount}回完了
                </strong>
              </div>

              {#if captureKind === 'enrollment'}
                <p>
                  3回の特徴を平均して代表声紋だけを暗号化保存します。元音声と各回の特徴は処理後すぐ削除します。
                </p>
              {/if}

              {#if recordingSupported}
                <div class="voice-recorder__actions">
                  {#if recording}
                    <Button variant="danger" onclick={stopRecording}
                      >録音を停止</Button
                    >
                  {:else}
                    <Button
                      variant="secondary"
                      onclick={startRecording}
                      loading={recordingStarting}
                      disabled={busy ||
                        capturedSamples.length >= requiredSampleCount}
                      >録音を開始</Button
                    >
                  {/if}
                  <span
                    class:voice-recorder__status--active={recording}
                    class="voice-recorder__status"
                    aria-live="polite"
                  >
                    {recording
                      ? `録音中 ${recordingSeconds}秒 / ${MAX_VOICE_RECORDING_SECONDS}秒`
                      : recordingStarting
                        ? 'マイクを準備中'
                        : capturedSamples.length >= requiredSampleCount
                          ? '必要な回数の録音が完了'
                          : `${capturedSamples.length + 1}回目の録音待ち`}
                  </span>
                </div>
              {:else}
                <p>
                  このブラウザではマイク録音を利用できません。下のファイル選択を使ってください。
                </p>
              {/if}

              {#if capturedSamples.length > 0}
                <ol class="voice-sample-list" aria-label="録音済みの音声">
                  {#each capturedSamples as sample, index (sample.previewUrl)}
                    <li class="voice-sample-card">
                      <div>
                        <strong>{index + 1}回目</strong>
                        <small>
                          {sample.durationSeconds === null
                            ? sample.file.name
                            : `${sample.durationSeconds}秒`}
                        </small>
                      </div>
                      <audio
                        class="voice-recorder__preview"
                        controls
                        src={sample.previewUrl}
                        aria-label={`${index + 1}回目の音声を再生`}
                      ></audio>
                      <Button
                        variant="tertiary"
                        size="compact"
                        onclick={() => removeCapturedSample(index)}
                        disabled={busy || recordingStarting || recording}
                        >録り直す</Button
                      >
                    </li>
                  {/each}
                </ol>
              {/if}
            </div>

            <details class="voice-file-fallback">
              <summary>録音済みの音声ファイルを選ぶ</summary>
              <label class="voice-file">
                <span>先生本人の音声ファイル（{requiredSampleCount}件）</span>
                <input
                  type="file"
                  accept="audio/*"
                  multiple={requiredSampleCount > 1}
                  onchange={chooseAudio}
                  disabled={busy || recordingStarting || recording}
                />
                <small
                  >選択した音声は処理完了・失敗・期限切れの時点でサーバーから削除されます。</small
                >
              </label>
            </details>

            <div class="voice-actions">
              <Button
                onclick={() => submitVoiceprint(captureKind)}
                loading={busy}
                disabled={recordingStarting ||
                  recording ||
                  capturedSamples.length !== requiredSampleCount}
                >{captureKind === 'enrollment'
                  ? `3回の音声で声紋を${voiceprint ? '再登録' : '登録'}`
                  : 'この音声で本人確認'}</Button
              >
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
