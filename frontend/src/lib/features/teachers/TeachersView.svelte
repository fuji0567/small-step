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

  import { TeachersService } from './service';
  import type { TeacherConfirmation, TeacherRead, TeacherRole } from './types';
  import './teachers.css';

  type Props = {
    api: ApiClient;
    appController: AppController;
    schoolId: string | null;
    isSchoolAdmin: boolean;
    currentTeacherId: string | null;
  };

  let { api, appController, schoolId, isSchoolAdmin, currentTeacherId }: Props =
    $props();
  const service = $derived(new TeachersService(api));
  let teachers = $state.raw<TeacherRead[]>([]);
  let loading = $state(false);
  let busy = $state(false);
  let errorMessage = $state<string | null>(null);
  let successMessage = $state<string | null>(null);
  let name = $state('');
  let email = $state('');
  let confirmation = $state<TeacherConfirmation | null>(null);
  let requestVersion = 0;

  const confirmationTitle = $derived.by(() => {
    if (!confirmation) return '';
    if (confirmation.kind === 'disable')
      return `${confirmation.teacher.name}先生を利用停止にしますか？`;
    if (confirmation.kind === 'restore')
      return `${confirmation.teacher.name}先生の利用を再開しますか？`;
    return confirmation.nextRole === 'school_admin'
      ? `${confirmation.teacher.name}先生を管理者にしますか？`
      : `${confirmation.teacher.name}先生を通常の先生に戻しますか？`;
  });

  const confirmationDescription = $derived.by(() => {
    if (!confirmation) return '';
    if (confirmation.kind === 'disable')
      return 'ログイン、担当の録音端末、待機中の音声処理を停止します。記録と通知の履歴は残ります。以前の端末キーや声紋同意は復帰後も戻りません。';
    if (confirmation.kind === 'restore')
      return 'ログインを再開できます。以前の録音端末、待機中音声、声紋同意は再開されません。';
    return confirmation.nextRole === 'school_admin'
      ? '園児・保護者、先生、録音端末、通知、操作履歴を管理できるようになります。'
      : '管理者向け操作ができなくなります。別の有効な先生管理者が必要です。';
  });

  async function load(signal?: AbortSignal): Promise<void> {
    const selectedSchoolId = schoolId;
    const version = ++requestVersion;
    if (!selectedSchoolId || !isSchoolAdmin) {
      teachers = [];
      return;
    }
    loading = true;
    errorMessage = null;
    try {
      const nextTeachers = await service.list(selectedSchoolId, signal);
      if (version === requestVersion) teachers = nextTeachers;
    } catch {
      if (signal?.aborted || version !== requestVersion) return;
      errorMessage = '先生一覧を取得できませんでした。';
    } finally {
      if (version === requestVersion) loading = false;
    }
  }

  async function refresh(): Promise<void> {
    await appController.refresh(['teachers']);
  }

  async function createTeacher(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    const selectedSchoolId = schoolId;
    const normalizedName = name.trim();
    const normalizedEmail = email.trim();
    if (!selectedSchoolId || !normalizedName || !normalizedEmail || busy)
      return;
    busy = true;
    errorMessage = null;
    try {
      await service.create(selectedSchoolId, normalizedName, normalizedEmail);
      name = '';
      email = '';
      successMessage =
        '先生を登録しました。同じメールアドレスへSupabaseから招待を送ってください。';
      await refresh();
    } catch {
      errorMessage =
        '先生を登録できませんでした。メールアドレスの重複などを確認してください。';
    } finally {
      busy = false;
    }
  }

  function ask(action: TeacherConfirmation): void {
    if (
      (action.kind === 'disable' || action.kind === 'role') &&
      action.teacher.id === currentTeacherId
    )
      return;
    confirmation = action;
    successMessage = null;
  }

  async function performConfirmation(): Promise<void> {
    const action = confirmation;
    if (!action || busy) return;
    busy = true;
    errorMessage = null;
    try {
      if (action.kind === 'disable') {
        await service.disable(action.teacher.id);
        successMessage =
          '先生アカウントを利用停止にしました。履歴は保持されています。';
      } else if (action.kind === 'restore') {
        await service.restore(action.teacher.id);
        successMessage = '先生アカウントの利用を再開しました。';
      } else {
        await service.changeRole(action.teacher.id, action.nextRole);
        successMessage =
          action.nextRole === 'school_admin'
            ? '先生を管理者にしました。'
            : '先生を通常の先生に戻しました。';
      }
      await refresh();
    } catch {
      errorMessage =
        '操作を完了できませんでした。管理者の人数や対象の状態を確認してください。';
    } finally {
      busy = false;
      confirmation = null;
    }
  }

  function roleLabel(role: TeacherRole): string {
    return role === 'school_admin' ? '先生管理者' : '先生';
  }

  $effect(() => {
    const unregister = appController.register('teachers', () => load());
    return unregister;
  });

  $effect(() => {
    const currentSchool = schoolId;
    const currentRole = isSchoolAdmin;
    void currentSchool;
    void currentRole;
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  });
</script>

<section class="teachers-page" aria-labelledby="teachers-heading">
  <header class="teachers-heading">
    <h2 id="teachers-heading">先生管理</h2>
    <p>先生を事前登録し、権限と利用状態を管理します。</p>
  </header>

  {#if !isSchoolAdmin}
    <Notice tone="warning" title="先生管理者専用です"
      ><p>この画面を利用する権限がありません。</p></Notice
    >
  {:else if !schoolId}
    <Notice tone="warning" title="園を選択してください"
      ><p>園を選択すると先生を管理できます。</p></Notice
    >
  {:else}
    <form class="teachers-form" onsubmit={createTeacher}>
      <div class="teachers-field">
        <label for="teacher-name">先生名</label>
        <input id="teacher-name" maxlength="120" required bind:value={name} />
      </div>
      <div class="teachers-field">
        <label for="teacher-email">メールアドレス</label>
        <input
          id="teacher-email"
          type="email"
          maxlength="320"
          required
          bind:value={email}
        />
      </div>
      <Button type="submit" loading={busy}>先生を登録</Button>
    </form>

    {#if successMessage}<Notice tone="success"><p>{successMessage}</p></Notice
      >{/if}
    {#if errorMessage}<Notice tone="error" title="操作できませんでした"
        ><p>{errorMessage}</p></Notice
      >{/if}

    <div class="teachers-toolbar">
      <StatusBadge
        label={`${teachers.filter((teacher) => teacher.is_active).length}人利用中`}
        tone="info"
      />
      <Button variant="secondary" onclick={() => refresh()} disabled={loading}
        >再読み込み</Button
      >
    </div>

    {#if loading}
      <Loading label="先生一覧を読み込んでいます" />
    {:else if teachers.length === 0}
      <div class="teachers-empty"><p>登録されている先生はいません。</p></div>
    {:else}
      <ul class="teachers-list">
        {#each teachers as teacher (teacher.id)}
          <li>
            <article
              class:teachers-card--inactive={!teacher.is_active}
              class="teachers-card"
            >
              <div class="teachers-card-heading">
                <div>
                  <h3>
                    {teacher.name}先生 {teacher.id === currentTeacherId
                      ? '（自分）'
                      : ''}
                  </h3>
                  <p>{teacher.email ?? 'メールアドレス未登録'}</p>
                </div>
                <div class="teachers-statuses">
                  <StatusBadge
                    label={roleLabel(teacher.role)}
                    tone={teacher.role === 'school_admin' ? 'info' : 'neutral'}
                  />
                  <StatusBadge
                    label={teacher.is_active ? '利用中' : '利用停止'}
                    tone={teacher.is_active ? 'success' : 'error'}
                  />
                  <StatusBadge
                    label={teacher.is_auth_linked ? '認証連携済み' : '招待待ち'}
                    tone={teacher.is_auth_linked ? 'success' : 'warning'}
                  />
                </div>
              </div>
              <div class="teachers-actions">
                {#if teacher.is_active}
                  {#if teacher.id === currentTeacherId}
                    <p class="teachers-self-note">
                      自分自身の権限変更・利用停止はできません。
                    </p>
                  {:else}
                    <Button
                      size="compact"
                      variant="secondary"
                      onclick={() =>
                        ask({
                          kind: 'role',
                          teacher,
                          nextRole:
                            teacher.role === 'school_admin'
                              ? 'teacher'
                              : 'school_admin'
                        })}
                    >
                      {teacher.role === 'school_admin'
                        ? '通常の先生に戻す'
                        : '管理者にする'}
                    </Button>
                    <Button
                      size="compact"
                      variant="danger"
                      onclick={() => ask({ kind: 'disable', teacher })}
                      >利用停止</Button
                    >
                  {/if}
                {:else}
                  <Button
                    size="compact"
                    variant="secondary"
                    onclick={() => ask({ kind: 'restore', teacher })}
                    >利用を再開</Button
                  >
                {/if}
              </div>
            </article>
          </li>
        {/each}
      </ul>
    {/if}
  {/if}
</section>

<ConfirmDialog
  open={confirmation !== null}
  title={confirmationTitle}
  description={confirmationDescription}
  tone={confirmation?.kind === 'disable' ? 'danger' : 'default'}
  {busy}
  onConfirm={performConfirmation}
  onCancel={() => (confirmation = null)}
/>
