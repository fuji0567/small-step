<script lang="ts">
  import { ApiHttpError, type ApiClient } from '$lib/api';
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
    invitationsEnabled?: boolean;
  };

  let {
    api,
    appController,
    schoolId,
    isSchoolAdmin,
    currentTeacherId,
    invitationsEnabled = false
  }: Props = $props();
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
    successMessage = null;
    try {
      const created = await service.create(
        selectedSchoolId,
        normalizedName,
        normalizedEmail
      );
      if (selectedSchoolId !== schoolId) return;
      name = '';
      email = '';
      if (invitationsEnabled) {
        try {
          await service.invite(created.id);
          if (selectedSchoolId !== schoolId) return;
          successMessage =
            '先生を登録し、招待メールの送信を受け付けました。メールからパスワードを設定してください。';
        } catch (error) {
          if (selectedSchoolId !== schoolId) return;
          successMessage = '先生の登録は完了しています。';
          errorMessage = invitationError(error);
        }
      } else {
        successMessage =
          '先生を登録しました。アプリからの招待送信は未設定です。同じメールアドレスへSupabaseから招待を送ってください。';
      }
      const invitationFailure = errorMessage;
      await refresh();
      if (selectedSchoolId === schoolId && invitationFailure)
        errorMessage = invitationFailure;
    } catch {
      errorMessage =
        '先生を登録できませんでした。メールアドレスの重複などを確認してください。';
    } finally {
      busy = false;
    }
  }

  function invitationError(error: unknown): string {
    if (error instanceof ApiHttpError && error.status === 429)
      return '招待メールの送信間隔・送信上限に達しています。少し待ってから再試行してください。';
    if (error instanceof ApiHttpError && error.status === 409)
      return '既存のログインアカウントがあるか、先生の状態が変わっています。登録済みのパスワードでログインするか、一覧を再読み込みしてください。';
    return '招待メールの送信を確認できませんでした。先生の登録は残っています。メールが届いていない場合は、1分以上待って一覧から再送してください。';
  }

  async function inviteTeacher(teacher: TeacherRead): Promise<void> {
    if (busy) return;
    const selectedSchoolId = schoolId;
    busy = true;
    errorMessage = null;
    successMessage = null;
    try {
      await service.invite(teacher.id);
      if (selectedSchoolId !== schoolId) return;
      successMessage =
        '招待メールの送信を受け付けました。受信した先生はメールからパスワードを設定してください。';
      await refresh();
    } catch (error) {
      if (selectedSchoolId === schoolId) errorMessage = invitationError(error);
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
    <p>先生を登録し、招待・権限・利用状態を管理します。</p>
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
      <Button type="submit" loading={busy}
        >{invitationsEnabled ? '登録して招待を送る' : '先生を登録'}</Button
      >
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
                    label={teacher.is_auth_linked
                      ? '認証連携済み'
                      : teacher.invitation_sent_at
                        ? '招待送信済み（ログイン待ち）'
                        : '招待待ち'}
                    tone={teacher.is_auth_linked ? 'success' : 'warning'}
                  />
                </div>
              </div>
              <div class="teachers-actions">
                {#if teacher.is_active}
                  {#if invitationsEnabled && !teacher.is_auth_linked && teacher.email}
                    <Button
                      size="compact"
                      variant="secondary"
                      disabled={busy}
                      onclick={() => inviteTeacher(teacher)}
                      guide="登録済みのメールアドレスへ招待を送ります。再送は1分以上空けてください。"
                    >
                      {teacher.invitation_sent_at
                        ? '招待メールを再送'
                        : '招待メールを送る'}
                    </Button>
                  {/if}
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
                      guide={teacher.role === 'school_admin'
                        ? '通常の先生に戻し、園全体の管理操作をできないようにします。'
                        : '園児・先生・端末・通知などの管理操作を許可します。'}
                    >
                      {teacher.role === 'school_admin'
                        ? '通常の先生に戻す'
                        : '管理者にする'}
                    </Button>
                    <Button
                      size="compact"
                      variant="danger"
                      onclick={() => ask({ kind: 'disable', teacher })}
                      guide="この先生のログインと担当端末の利用を停止します。履歴は残ります。"
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
