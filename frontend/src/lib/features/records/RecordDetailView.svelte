<script lang="ts">
  import { resolve } from '$app/paths';
  import type { Pathname } from '$app/types';
  import { onMount } from 'svelte';

  import { ApiHttpError, type ApiClient } from '$lib/api';
  import {
    Button,
    ConfirmDialog,
    Loading,
    Notice,
    StatusBadge
  } from '$lib/components';

  import {
    categoryLabel,
    formatDateTime,
    localDateTimeValue,
    recordDetailPath,
    statusLabel
  } from './format';
  import './records.css';
  import { RecordsService } from './service';
  import type {
    ChildSuggestionRead,
    RecordChild,
    RecordRead,
    RecordReviewInput,
    RecordTeacher
  } from './types';

  type Props = {
    api: ApiClient;
    schoolId: string | null;
    recordId: string;
    isSchoolAdmin?: boolean;
    onNavigate: (path: Pathname) => void | Promise<void>;
    onReassigned?: () => void | Promise<void>;
  };

  let {
    api,
    schoolId,
    recordId,
    isSchoolAdmin = false,
    onNavigate,
    onReassigned
  }: Props = $props();
  const service = $derived(new RecordsService(api));
  let record = $state<RecordRead | null>(null);
  let voiceprintSuggestion = $state<{
    status: 'disabled' | 'unidentified' | 'candidate';
    teacher_id: string | null;
    teacher_name: string | null;
  } | null>(null);
  let children = $state.raw<RecordChild[]>([]);
  let teachers = $state.raw<RecordTeacher[]>([]);
  let summary = $state('');
  let conversationPrompt = $state('');
  let childId = $state('');
  let childConfirmed = $state(false);
  let childTouched = false;
  let childSuggestion = $state<ChildSuggestionRead | null>(null);
  let scheduledEnabled = $state(false);
  let scheduledFor = $state('');
  let loading = $state(false);
  let saving = $state(false);
  let assigning = $state(false);
  let assigneeId = $state('');
  let errorMessage = $state<string | null>(null);
  let successMessage = $state<string | null>(null);
  let errorStatus = $state<number | null>(null);
  let confirmation = $state<'approve' | 'reject' | null>(null);
  let assignmentConfirmation = $state(false);
  let requestVersion = 0;

  const isPending = $derived(record?.status === 'pending_review');
  const needsChildConfirmation = $derived(
    Boolean(record?.source_event_id?.startsWith('recorder-session-'))
  );
  const dirty = $derived(
    isPending &&
      (summary !== (record?.summary ?? '') ||
        conversationPrompt !== (record?.conversation_prompt ?? '') ||
        childId !== (record?.child_id ?? '') ||
        scheduledEnabled)
  );
  const activeChildren = $derived(children.filter((child) => child.is_active));
  const currentAssignee = $derived(
    teachers.find((teacher) => teacher.id === record?.teacher_id)
  );
  const selectedAssignee = $derived(
    teachers.find((teacher) => teacher.id === assigneeId)
  );
  const canReassign = $derived(
    isSchoolAdmin &&
      isPending &&
      Boolean(selectedAssignee?.is_active) &&
      assigneeId !== record?.teacher_id
  );

  function applyRecord(nextRecord: RecordRead): void {
    record = nextRecord;
    summary = nextRecord.summary;
    conversationPrompt = nextRecord.conversation_prompt ?? '';
    childId = nextRecord.child_id ?? '';
    childConfirmed = false;
    childTouched = false;
    assigneeId = nextRecord.teacher_id;
    scheduledEnabled = false;
    scheduledFor = localDateTimeValue();
  }

  function loadError(error: unknown): void {
    errorStatus = error instanceof ApiHttpError ? error.status : null;
    if (errorStatus === 403) {
      errorMessage = 'この日誌を確認する権限がありません。';
    } else if (errorStatus === 404) {
      errorMessage = '指定された日誌は見つかりませんでした。';
    } else {
      errorMessage =
        error instanceof Error ? error.message : '日誌を取得できませんでした。';
    }
  }

  async function load(signal?: AbortSignal): Promise<void> {
    const selectedRecordId = recordId;
    const selectedSchoolId = schoolId;
    const version = ++requestVersion;
    record = null;
    voiceprintSuggestion = null;
    childSuggestion = null;
    errorMessage = null;
    successMessage = null;
    errorStatus = null;
    if (!selectedSchoolId) return;
    loading = true;
    try {
      const [nextRecord, nextChildren, nextTeachers] = await Promise.all([
        service.get(selectedRecordId, signal),
        service.listChildren(selectedSchoolId, signal),
        isSchoolAdmin
          ? service.listTeachers(selectedSchoolId, signal)
          : Promise.resolve([])
      ]);
      if (version !== requestVersion) return;
      children = nextChildren;
      teachers = nextTeachers;
      applyRecord(nextRecord);
      loading = false;
      // Independent of voiceprint advice; late results must not overwrite edits.
      if (
        nextRecord.status === 'pending_review' &&
        nextRecord.child_id === null &&
        nextRecord.source_event_id?.startsWith('recorder-session-')
      ) {
        void api
          .requestJson<ChildSuggestionRead>(
            `/records/${selectedRecordId}/child-suggestion`,
            { signal }
          )
          .then((suggestion) => {
            if (version !== requestVersion || signal?.aborted) return;
            childSuggestion = suggestion;
            if (
              !childTouched &&
              suggestion?.status === 'candidate' &&
              nextChildren.some(
                (child) => child.id === suggestion.child_id && child.is_active
              )
            ) {
              childId = suggestion.child_id ?? '';
              childConfirmed = false;
            }
          })
          .catch(() => {
            /* Optional advice must not block manual selection. */
          });
      }
      try {
        const suggestion = await api.requestJson<typeof voiceprintSuggestion>(
          `/records/${selectedRecordId}/voiceprint-suggestion`,
          { signal }
        );
        if (version === requestVersion) voiceprintSuggestion = suggestion;
      } catch {
        // Optional identity advice must never block the human review screen.
      }
    } catch (error) {
      if (signal?.aborted || version !== requestVersion) return;
      loadError(error);
    } finally {
      if (version === requestVersion) loading = false;
    }
  }

  async function reassignRecord(): Promise<void> {
    if (!record || !canReassign) return;
    assigning = true;
    errorMessage = null;
    successMessage = null;
    try {
      const nextRecord = await service.reassign(record.id, {
        teacher_id: assigneeId
      });
      record = nextRecord;
      assigneeId = nextRecord.teacher_id;
      successMessage = `${selectedAssignee?.name ?? '選択した先生'}へ担当を引き継ぎました。`;
    } catch (error) {
      errorMessage =
        error instanceof ApiHttpError &&
        error.status !== null &&
        [409, 422].includes(error.status)
          ? '担当を変更できませんでした。記録と先生の状態を再読み込みして確認してください。'
          : error instanceof Error
            ? error.message
            : '担当を変更できませんでした。';
      return;
    } finally {
      assigning = false;
      assignmentConfirmation = false;
    }
    try {
      await onReassigned?.();
    } catch {
      // Badge refresh is supplemental; the assignment itself has succeeded.
    }
  }

  function requestBack(event: MouseEvent): void {
    if (dirty && !globalThis.confirm('編集内容を破棄して一覧へ戻りますか？')) {
      event.preventDefault();
    }
  }

  function reviewInput(): RecordReviewInput | null {
    if (needsChildConfirmation && (!childId || !childConfirmed)) {
      errorMessage =
        '選択した園児がこの出来事の対象であることを確認してください。';
      return null;
    }
    const normalizedSummary = summary.trim();
    if (!normalizedSummary) {
      errorMessage = '保護者へ伝える内容を入力してください。';
      return null;
    }
    const input: RecordReviewInput = { summary: normalizedSummary };
    if (childId) input.child_id = childId;
    if (needsChildConfirmation) input.child_confirmed = childConfirmed;
    const normalizedPrompt = conversationPrompt.trim();
    if (normalizedPrompt) input.conversation_prompt = normalizedPrompt;
    if (scheduledEnabled) {
      const timestamp = Date.parse(scheduledFor);
      if (!scheduledFor || !Number.isFinite(timestamp)) {
        errorMessage = '配信日時を入力してください。';
        return null;
      }
      input.scheduled_for = new Date(timestamp).toISOString();
    }
    return input;
  }

  async function finishReview(action: 'approve' | 'reject'): Promise<void> {
    if (!record || record.status !== 'pending_review') return;
    const reviewedId = record.id;
    const input = action === 'approve' ? reviewInput() : null;
    if (action === 'approve' && !input) return;
    saving = true;
    errorMessage = null;
    try {
      if (action === 'approve') await service.approve(reviewedId, input!);
      else await service.reject(reviewedId);

      const nextPending = await service.listPending(record.school_id);
      const next = nextPending.find((candidate) => candidate.id !== reviewedId);
      await onNavigate(next ? recordDetailPath(next.id) : '/teacher/review/');
    } catch (error) {
      loadError(error);
      if (error instanceof ApiHttpError && error.status === 409) {
        await load();
      }
    } finally {
      saving = false;
      confirmation = null;
    }
  }

  onMount(() => {
    const warnBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!dirty) return;
      event.preventDefault();
      event.returnValue = '';
    };
    globalThis.addEventListener('beforeunload', warnBeforeUnload);
    return () =>
      globalThis.removeEventListener('beforeunload', warnBeforeUnload);
  });

  $effect(() => {
    const currentRecord = recordId;
    const currentSchool = schoolId;
    const currentAdminAccess = isSchoolAdmin;
    void currentRecord;
    void currentSchool;
    void currentAdminAccess;
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  });
</script>

<section class="records-page" aria-labelledby="record-detail-heading">
  <header class="records-heading">
    <a
      class="records-link"
      href={resolve('/teacher/review/')}
      onclick={requestBack}>レビュー待ち一覧へ戻る</a
    >
    <h2 id="record-detail-heading">日誌のレビュー</h2>
    <p>日誌IDだけをURLに含め、園児名や本文はURLへ保存しません。</p>
  </header>

  {#if loading}
    <Loading label="日誌を読み込んでいます" />
  {:else if errorMessage && !record}
    <Notice
      tone="error"
      title={errorStatus === 404 ? '日誌が見つかりません' : '日誌を開けません'}
    >
      <p>{errorMessage}</p>
    </Notice>
  {:else if !schoolId}
    <Notice tone="warning" title="園を選択してください">
      <p>園を選択してから日誌を開いてください。</p>
    </Notice>
  {:else if record}
    {#if record.is_trial}
      <Notice tone="warning" title="試用記録（保護者への配信なし）"
        ><p>
          承認してもLINEには送信しません。本番へ切り替えてもこの記録は配信されません。
        </p></Notice
      >
    {/if}
    {#if !isSchoolAdmin}
      <Notice tone="info" title="自分が担当する日誌です">
        <p>一般の先生には、自分に割り当てられた日誌だけを表示します。</p>
      </Notice>
    {/if}
    {#if record.status !== 'pending_review'}
      <Notice tone="warning" title="この日誌は処理済みです">
        <p>
          現在の状態は「{statusLabel(
            record.status
          )}」です。内容は参照できますが、再度承認・却下はできません。
        </p>
      </Notice>
    {/if}
    {#if errorMessage}
      <Notice tone="error" title="操作を完了できませんでした">
        <p>{errorMessage}</p>
      </Notice>
    {/if}
    {#if successMessage}
      <Notice tone="success" title="担当を変更しました">
        <p>{successMessage}</p>
      </Notice>
    {/if}

    <article class="records-card">
      <div class="records-card-header">
        <StatusBadge label={categoryLabel(record.category)} tone="info" />
        <StatusBadge
          label={statusLabel(record.status)}
          tone={record.status === 'pending_review' ? 'warning' : 'neutral'}
        />
      </div>
      <p class="records-meta">
        発生: {formatDateTime(record.occurred_at)}・信頼度 {Math.round(
          record.confidence * 100
        )}%
      </p>
      {#if record.audio_processing_incomplete}
        <Notice tone="warning" title="一部の音声を処理できませんでした">
          <p>
            この記録は処理できた区間だけで作成されています。内容と抜け漏れを確認してから承認してください。
          </p>
        </Notice>
      {/if}

      {#if voiceprintSuggestion && voiceprintSuggestion.status !== 'disabled'}
        <Notice tone="info" title="録音の声紋照合">
          {#if voiceprintSuggestion.status === 'candidate'}
            <p>担当候補: {voiceprintSuggestion.teacher_name}さん</p>
            <p>
              録音内の声から得た候補です。本人や記録の担当を確定するものではありません。現在の担当は変更されていません。
            </p>
            {#if isSchoolAdmin && isPending && teachers.some((teacher) => teacher.id === voiceprintSuggestion?.teacher_id && teacher.is_active)}
              <Button
                variant="secondary"
                disabled={saving || assigning}
                onclick={() => {
                  assigneeId = voiceprintSuggestion?.teacher_id ?? assigneeId;
                }}>候補を引き継ぎ先に選択</Button
              >
              <p>下の「担当を変更」で内容を確認してから引き継いでください。</p>
            {/if}
          {:else}
            <p>
              先生未特定。未登録、同意対象外、短い発話、照合の不一致・曖昧さなどでは候補を表示しません。
            </p>
          {/if}
        </Notice>
      {/if}

      {#if isSchoolAdmin}
        <section
          class="records-assignment"
          aria-labelledby="record-assignment-heading"
        >
          <div>
            <h3 id="record-assignment-heading">担当の割り当て・引き継ぎ</h3>
            <p class="records-meta">
              現在の担当: {currentAssignee?.name ??
                '担当先生を確認できません'}{currentAssignee &&
              !currentAssignee.is_active
                ? '（利用停止中）'
                : ''}
            </p>
          </div>
          {#if isPending}
            <div class="records-assignment-controls">
              <div class="records-field">
                <label for="record-assignee">引き継ぎ先の先生</label>
                <select
                  id="record-assignee"
                  class="records-control"
                  bind:value={assigneeId}
                  disabled={saving || assigning}
                >
                  {#each teachers as teacher (teacher.id)}
                    <option value={teacher.id} disabled={!teacher.is_active}
                      >{teacher.name}{teacher.is_active
                        ? ''
                        : '（利用停止中）'}</option
                    >
                  {/each}
                </select>
              </div>
              <Button
                variant="secondary"
                onclick={() => (assignmentConfirmation = true)}
                guide="選択した先生のレビュー待ち一覧へ、この日誌を移します。"
                disabled={!canReassign || saving}
                loading={assigning}>担当を変更</Button
              >
            </div>
          {:else}
            <p class="records-support">
              承認・却下・配信済みの記録は、履歴を保つため担当を変更できません。
            </p>
          {/if}
        </section>
      {/if}

      <form class="records-form" onsubmit={(event) => event.preventDefault()}>
        <div class="records-field">
          <label for="record-child">園児</label>
          {#if childSuggestion?.status === 'candidate'}
            <Notice tone="info"
              ><p>
                録音からの園児候補: {childSuggestion.child_name}。自動選択は仮の候補です。名前と出来事の対象を確認してください。
              </p></Notice
            >
          {/if}
          <select
            id="record-child"
            class="records-control"
            bind:value={childId}
            onchange={() => {
              childTouched = true;
              childConfirmed = false;
            }}
            disabled={!isPending || saving || assigning}
          >
            <option value="">未選択</option>
            {#each activeChildren as child (child.id)}
              <option value={child.id}>{child.display_name}</option>
            {/each}
          </select>
          {#if isPending && needsChildConfirmation}
            <label
              ><input
                type="checkbox"
                bind:checked={childConfirmed}
                disabled={!childId || saving || assigning}
              /> 選択した園児がこの出来事の対象であることを確認しました</label
            >
          {/if}
        </div>
        <div class="records-field">
          <label for="record-summary">保護者へ伝える内容</label>
          <textarea
            id="record-summary"
            class="records-control"
            maxlength="4000"
            bind:value={summary}
            disabled={!isPending || saving || assigning}></textarea>
          <span class="records-support">{summary.length}/4000文字</span>
        </div>
        <div class="records-field">
          <label for="record-prompt">会話のきっかけ（任意）</label>
          <textarea
            id="record-prompt"
            class="records-control"
            maxlength="4000"
            bind:value={conversationPrompt}
            disabled={!isPending || saving || assigning}></textarea>
        </div>
        {#if isPending}
          <div class="records-field">
            <label
              ><input
                type="checkbox"
                bind:checked={scheduledEnabled}
                disabled={saving || assigning}
              /> 配信日時を指定する</label
            >
            {#if scheduledEnabled}
              <input
                aria-label="配信日時"
                class="records-control"
                type="datetime-local"
                bind:value={scheduledFor}
                disabled={saving || assigning}
              />
            {/if}
          </div>
          <div class="records-actions">
            <Button
              onclick={() => (confirmation = 'approve')}
              guide={record.is_trial
                ? '編集内容を保存します。試用記録は配信しません。'
                : '編集内容を保存し、保護者へのLINE通知を準備します。'}
              disabled={saving ||
                assigning ||
                (needsChildConfirmation && (!childId || !childConfirmed))}
              >承認する</Button
            >
            <Button
              variant="danger"
              onclick={() => (confirmation = 'reject')}
              guide="確認待ちから外します。保護者には通知されません。"
              disabled={saving || assigning}>却下する</Button
            >
          </div>
        {/if}
      </form>
    </article>
  {/if}
</section>

<ConfirmDialog
  open={confirmation !== null}
  title={confirmation === 'reject'
    ? '日誌を却下しますか？'
    : '日誌を承認しますか？'}
  description={confirmation === 'reject'
    ? 'この日誌はレビュー待ちの一覧から外れます。'
    : record?.is_trial
      ? '編集内容を保存します。試用記録のため、保護者への配信は行いません。'
      : '編集内容を保存し、保護者への通知を準備します。'}
  confirmLabel={confirmation === 'reject' ? '却下する' : '承認する'}
  tone={confirmation === 'reject' ? 'danger' : 'default'}
  busy={saving}
  onConfirm={() => finishReview(confirmation ?? 'approve')}
  onCancel={() => (confirmation = null)}
/>

<ConfirmDialog
  bind:open={assignmentConfirmation}
  title="担当を変更しますか？"
  description={`${selectedAssignee?.name ?? '選択した先生'}のレビュー待ち一覧へ、この日誌を移します。日誌の本文は変更されません。`}
  confirmLabel="担当を変更"
  busy={assigning}
  onConfirm={reassignRecord}
  onCancel={() => (assignmentConfirmation = false)}
/>
