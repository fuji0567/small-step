<script lang="ts">
  import { onMount } from 'svelte';
  import { resolve } from '$app/paths';
  import type { Pathname } from '$app/types';

  import type { ApiClient, RecordCategory } from '$lib/api';
  import { Button, Loading, Notice } from '$lib/components';

  import { localDateTimeValue, recordDetailPath } from './format';
  import './records.css';
  import { RecordsService } from './service';
  import type { RecordChild, RecordTeacher } from './types';

  type Props = {
    api: ApiClient;
    schoolId: string | null;
    currentTeacherId: string | null;
    onNavigate: (path: Pathname) => void | Promise<void>;
  };

  let { api, schoolId, currentTeacherId, onNavigate }: Props = $props();
  const service = $derived(new RecordsService(api));
  let children = $state.raw<RecordChild[]>([]);
  let teachers = $state.raw<RecordTeacher[]>([]);
  let childId = $state('');
  let teacherId = $state('');
  let category = $state<RecordCategory>('growth');
  let occurredAt = $state(localDateTimeValue());
  let summary = $state('');
  let conversationPrompt = $state('');
  let loading = $state(false);
  let saving = $state(false);
  let errorMessage = $state<string | null>(null);
  let submitted = $state(false);
  let requestVersion = 0;

  const requiresTeacherSelection = $derived(currentTeacherId === null);
  const dirty = $derived(
    !submitted &&
      (childId !== '' ||
        summary !== '' ||
        conversationPrompt !== '' ||
        category !== 'growth')
  );

  async function load(signal?: AbortSignal): Promise<void> {
    const selectedSchoolId = schoolId;
    const version = ++requestVersion;
    children = [];
    teachers = [];
    childId = '';
    teacherId = '';
    errorMessage = null;
    if (!selectedSchoolId) return;
    loading = true;
    try {
      const [nextChildren, nextTeachers] = await Promise.all([
        service.listChildren(selectedSchoolId, signal),
        requiresTeacherSelection
          ? service.listTeachers(selectedSchoolId, signal)
          : Promise.resolve([])
      ]);
      if (version !== requestVersion) return;
      children = nextChildren.filter((child) => child.is_active);
      teachers = nextTeachers.filter((teacher) => teacher.is_active);
      childId = children[0]?.id ?? '';
      teacherId = currentTeacherId ?? teachers[0]?.id ?? '';
    } catch (error) {
      if (signal?.aborted || version !== requestVersion) return;
      errorMessage =
        error instanceof Error
          ? error.message
          : '入力画面を準備できませんでした。';
    } finally {
      if (version === requestVersion) loading = false;
    }
  }

  function requestBack(event: MouseEvent): void {
    if (dirty && !globalThis.confirm('入力内容を破棄して一覧へ戻りますか？')) {
      event.preventDefault();
    }
  }

  async function submit(): Promise<void> {
    errorMessage = null;
    const occurredAtMilliseconds = Date.parse(occurredAt);
    if (!childId) {
      errorMessage = '園児を選択してください。';
      return;
    }
    if (requiresTeacherSelection && !teacherId) {
      errorMessage = '担当先生を選択してください。';
      return;
    }
    if (
      !Number.isFinite(occurredAtMilliseconds) ||
      occurredAtMilliseconds > Date.now()
    ) {
      errorMessage = '発生日時は現在以前の日時を入力してください。';
      return;
    }
    const normalizedSummary = summary.trim();
    if (!normalizedSummary) {
      errorMessage = '保護者へ伝える内容を入力してください。';
      return;
    }

    saving = true;
    try {
      const record = await service.createManual({
        school_id: schoolId!,
        ...(teacherId ? { teacher_id: teacherId } : {}),
        child_id: childId,
        category,
        occurred_at: new Date(occurredAtMilliseconds).toISOString(),
        summary: normalizedSummary,
        ...(conversationPrompt.trim()
          ? { conversation_prompt: conversationPrompt.trim() }
          : {})
      });
      submitted = true;
      await onNavigate(recordDetailPath(record.id));
    } catch (error) {
      errorMessage =
        error instanceof Error ? error.message : '日誌を追加できませんでした。';
    } finally {
      saving = false;
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
    const currentSchool = schoolId;
    const currentTeacher = currentTeacherId;
    void currentSchool;
    void currentTeacher;
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  });
</script>

<section class="records-page" aria-labelledby="manual-record-heading">
  <header class="records-heading">
    <a
      class="records-link"
      href={resolve('/teacher/review/')}
      onclick={requestBack}>レビュー待ち一覧へ戻る</a
    >
    <h2 id="manual-record-heading">日誌を手入力する</h2>
    <p>音声候補がないときも、同じレビュー手順で確認してから配信できます。</p>
  </header>

  {#if loading}
    <Loading label="入力画面を準備しています" />
  {:else if !schoolId}
    <Notice tone="warning" title="園を選択してください">
      <p>園を選択してから日誌を入力してください。</p>
    </Notice>
  {:else}
    {#if errorMessage}
      <Notice tone="error" title="入力内容を確認してください">
        <p>{errorMessage}</p>
      </Notice>
    {/if}
    {#if children.length === 0}
      <Notice tone="warning" title="在籍中の園児がいません">
        <p>先に「園児・保護者」画面で園児を登録してください。</p>
      </Notice>
    {:else}
      <form
        class="records-card records-form"
        onsubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <div class="records-field">
          <label for="manual-child">園児</label>
          <select
            id="manual-child"
            class="records-control"
            bind:value={childId}
            disabled={saving}
            required
          >
            {#each children as child (child.id)}
              <option value={child.id}>{child.display_name}</option>
            {/each}
          </select>
        </div>
        {#if requiresTeacherSelection}
          <div class="records-field">
            <label for="manual-teacher">担当先生</label>
            <select
              id="manual-teacher"
              class="records-control"
              bind:value={teacherId}
              disabled={saving}
              required
            >
              <option value="">選択してください</option>
              {#each teachers as teacher (teacher.id)}
                <option value={teacher.id}>{teacher.name}</option>
              {/each}
            </select>
          </div>
        {/if}
        <div class="records-field">
          <label for="manual-category">種別</label>
          <select
            id="manual-category"
            class="records-control"
            bind:value={category}
            disabled={saving}
          >
            <option value="growth">成長記録</option>
            <option value="injury">怪我</option>
          </select>
        </div>
        <div class="records-field">
          <label for="manual-occurred-at">発生日時</label>
          <input
            id="manual-occurred-at"
            class="records-control"
            type="datetime-local"
            bind:value={occurredAt}
            max={localDateTimeValue()}
            disabled={saving}
            required
          />
        </div>
        <div class="records-field">
          <label for="manual-summary">保護者へ伝える内容</label>
          <textarea
            id="manual-summary"
            class="records-control"
            bind:value={summary}
            maxlength="4000"
            disabled={saving}
            required></textarea>
          <span class="records-support">{summary.length}/4000文字</span>
        </div>
        <div class="records-field">
          <label for="manual-prompt">会話のきっかけ（任意）</label>
          <textarea
            id="manual-prompt"
            class="records-control"
            bind:value={conversationPrompt}
            maxlength="4000"
            disabled={saving}></textarea>
        </div>
        <div class="records-actions">
          <Button
            type="submit"
            loading={saving}
            disabled={children.length === 0}>レビュー待ちに追加</Button
          >
        </div>
      </form>
    {/if}
  {/if}
</section>
