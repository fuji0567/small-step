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

  import { ChildrenService } from './service';
  import type {
    ChildConfirmation,
    ChildRead,
    GuardianArchiveCredential,
    LineInvitationCredential,
    LineInvitationRead
  } from './types';
  import './children.css';

  type Props = {
    api: ApiClient;
    appController: AppController;
    schoolId: string | null;
    isSchoolAdmin: boolean;
  };

  let { api, appController, schoolId, isSchoolAdmin }: Props = $props();
  const service = $derived(new ChildrenService(api));
  let children = $state.raw<ChildRead[]>([]);
  let invitations = $state.raw<LineInvitationRead[]>([]);
  let loading = $state(false);
  let busy = $state(false);
  let errorMessage = $state<string | null>(null);
  let successMessage = $state<string | null>(null);
  let displayName = $state('');
  let editingChildId = $state<string | null>(null);
  let editingName = $state('');
  let confirmation = $state<ChildConfirmation | null>(null);
  let invitationCredential = $state<LineInvitationCredential | null>(null);
  let archiveCredential = $state<GuardianArchiveCredential | null>(null);
  let requestVersion = 0;

  const invitationByChild = $derived(
    new Map(invitations.map((invitation) => [invitation.child_id, invitation]))
  );

  const confirmationTitle = $derived.by(() => {
    if (!confirmation) return '';
    switch (confirmation.kind) {
      case 'archive':
        return `${confirmation.child.display_name}さんを退園処理しますか？`;
      case 'restore':
        return `${confirmation.child.display_name}さんを復園に戻しますか？`;
      case 'unlink':
        return `${confirmation.child.display_name}さんのLINE連携を解除しますか？`;
      case 'invitation':
        return confirmation.replacing
          ? '新しい招待コードを発行しますか？'
          : 'LINE招待コードを発行しますか？';
      case 'archive-link':
        return `${confirmation.child.display_name}さんのアーカイブURLを発行しますか？`;
    }
  });

  const confirmationDescription = $derived.by(() => {
    if (!confirmation) return '';
    switch (confirmation.kind) {
      case 'archive':
        return 'LINE連携、未使用の招待コード、保護者用URL、未確認の記録、未送信通知、未処理音声を停止します。過去の履歴は残ります。';
      case 'restore':
        return '在籍中へ戻しますが、以前のLINE連携、招待コード、保護者用URL、未送信通知、未処理音声は復活しません。';
      case 'unlink':
        return '未送信通知、未使用の招待コード、保護者用URLは無効になります。送信開始済みの通知は取り消せません。';
      case 'invitation':
        return confirmation.replacing
          ? '現在のコードはすぐ使えなくなります。新しいコードはこの画面で一度だけ表示します。'
          : 'コードはこの画面で一度だけ表示します。保護者本人へ個別に伝えてください。';
      case 'archive-link':
        return '以前のURLはすぐ使えなくなります。新しいURLはこの画面で一度だけ表示します。';
    }
  });

  function clearCredentials(): void {
    invitationCredential = null;
    archiveCredential = null;
  }

  async function load(signal?: AbortSignal): Promise<void> {
    const selectedSchoolId = schoolId;
    const version = ++requestVersion;
    editingChildId = null;
    if (!selectedSchoolId || !isSchoolAdmin) {
      children = [];
      invitations = [];
      return;
    }
    loading = true;
    errorMessage = null;
    try {
      const [nextChildren, nextInvitations] = await Promise.all([
        service.listChildren(selectedSchoolId, signal),
        service.listInvitations(selectedSchoolId, signal)
      ]);
      if (version !== requestVersion) return;
      children = nextChildren;
      invitations = nextInvitations;
    } catch {
      if (signal?.aborted || version !== requestVersion) return;
      errorMessage = '園児と保護者の情報を取得できませんでした。';
    } finally {
      if (version === requestVersion) loading = false;
    }
  }

  async function refresh(): Promise<void> {
    await appController.refresh(['children']);
  }

  async function createChild(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    const selectedSchoolId = schoolId;
    const name = displayName.trim();
    if (!selectedSchoolId || !name || busy) return;
    busy = true;
    errorMessage = null;
    try {
      await service.create(selectedSchoolId, name);
      displayName = '';
      successMessage = '園児を追加しました。';
      await refresh();
    } catch {
      errorMessage = '園児を追加できませんでした。入力内容を確認してください。';
    } finally {
      busy = false;
    }
  }

  function beginRename(child: ChildRead): void {
    editingChildId = child.id;
    editingName = child.display_name;
  }

  async function saveRename(childId: string): Promise<void> {
    const name = editingName.trim();
    if (!name || busy) return;
    busy = true;
    errorMessage = null;
    try {
      await service.rename(childId, name);
      editingChildId = null;
      successMessage =
        '園児の表示名を更新しました。過去の記録は保持されています。';
      await refresh();
    } catch {
      errorMessage = '表示名を更新できませんでした。';
    } finally {
      busy = false;
    }
  }

  function ask(action: ChildConfirmation): void {
    successMessage = null;
    confirmation = action;
  }

  async function performConfirmation(): Promise<void> {
    const action = confirmation;
    if (!action || busy) return;
    busy = true;
    errorMessage = null;
    try {
      if (action.kind === 'archive') {
        clearCredentials();
        await service.archive(action.child.id);
        successMessage =
          '退園処理を完了しました。新しい通知と音声処理は停止し、履歴は保持されています。';
      } else if (action.kind === 'restore') {
        clearCredentials();
        await service.restore(action.child.id);
        successMessage =
          '復園として在籍中へ戻しました。保護者LINEは新しい招待コードで連携してください。';
      } else if (action.kind === 'unlink') {
        clearCredentials();
        await service.unlinkGuardian(action.child.id);
        successMessage = '保護者LINEの連携を解除しました。';
      } else if (action.kind === 'invitation') {
        clearCredentials();
        invitationCredential = await service.issueInvitation(action.child.id);
        successMessage = action.replacing
          ? '新しい招待コードを発行しました。以前のコードは使えません。'
          : '招待コードを発行しました。';
      } else {
        clearCredentials();
        archiveCredential = await service.issueArchiveLink(action.child.id);
        successMessage = '保護者用URLを発行しました。以前のURLは使えません。';
      }
      await refresh();
    } catch {
      errorMessage =
        '操作を完了できませんでした。状態を確認して再試行してください。';
    } finally {
      busy = false;
      confirmation = null;
    }
  }

  async function copyCredential(
    value: string,
    kind: 'code' | 'url'
  ): Promise<void> {
    try {
      await navigator.clipboard.writeText(value);
      successMessage =
        kind === 'code'
          ? '招待コードをコピーしました。'
          : '保護者用URLをコピーしました。';
    } catch {
      errorMessage =
        'コピーできませんでした。表示内容を手動でコピーしてください。';
    }
  }

  function formatDate(value: string): string {
    return new Intl.DateTimeFormat('ja-JP', {
      dateStyle: 'medium',
      timeStyle: 'short'
    }).format(new Date(value));
  }

  $effect(() => {
    const unregister = appController.register('children', () => load());
    return unregister;
  });

  $effect(() => {
    const currentSchool = schoolId;
    const currentRole = isSchoolAdmin;
    void currentSchool;
    void currentRole;
    clearCredentials();
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  });
</script>

<section class="people-page" aria-labelledby="children-heading">
  <header class="people-heading">
    <h2 id="children-heading">園児・保護者</h2>
    <p>園児の在籍状況と保護者のLINE連携を管理します。</p>
  </header>

  {#if !isSchoolAdmin}
    <Notice tone="warning" title="先生管理者専用です">
      <p>この画面を利用する権限がありません。</p>
    </Notice>
  {:else if !schoolId}
    <Notice tone="warning" title="園を選択してください">
      <p>園を選択すると園児を管理できます。</p>
    </Notice>
  {:else}
    <form class="people-form" onsubmit={createChild}>
      <div class="people-field">
        <label for="child-display-name">園児の表示名</label>
        <input
          id="child-display-name"
          maxlength="120"
          required
          bind:value={displayName}
        />
      </div>
      <Button type="submit" loading={busy}>園児を追加</Button>
    </form>

    {#if successMessage}
      <Notice tone="success"><p>{successMessage}</p></Notice>
    {/if}
    {#if errorMessage}
      <Notice tone="error" title="操作できませんでした"
        ><p>{errorMessage}</p></Notice
      >
    {/if}
    {#if invitationCredential}
      <aside class="credential" aria-labelledby="invitation-credential-heading">
        <h3 id="invitation-credential-heading">LINE招待コード（今だけ表示）</h3>
        <p>有効期限: {formatDate(invitationCredential.expires_at)}</p>
        <output>{invitationCredential.invite_code}</output>
        <Button
          variant="secondary"
          onclick={() =>
            copyCredential(invitationCredential!.invite_code, 'code')}
          >コピー</Button
        >
      </aside>
    {/if}
    {#if archiveCredential}
      <aside class="credential" aria-labelledby="archive-credential-heading">
        <h3 id="archive-credential-heading">保護者用URL（今だけ表示）</h3>
        <p>有効期限: {formatDate(archiveCredential.expires_at)}</p>
        <output>{archiveCredential.archive_url}</output>
        <Button
          variant="secondary"
          onclick={() => copyCredential(archiveCredential!.archive_url, 'url')}
          >コピー</Button
        >
      </aside>
    {/if}

    <div class="people-toolbar">
      <StatusBadge
        label={`${children.filter((child) => child.is_active).length}人在籍`}
        tone="info"
      />
      <Button variant="secondary" onclick={() => refresh()} disabled={loading}
        >再読み込み</Button
      >
    </div>

    {#if loading}
      <Loading label="園児と保護者の情報を読み込んでいます" />
    {:else if children.length === 0}
      <div class="people-empty"><p>登録されている園児はいません。</p></div>
    {:else}
      <ul class="people-list">
        {#each children as child (child.id)}
          <li>
            <article
              class:people-card--inactive={!child.is_active}
              class="people-card"
            >
              <div class="people-card-heading">
                {#if editingChildId === child.id}
                  <div class="people-edit">
                    <label for={`child-name-${child.id}`}>表示名</label>
                    <input
                      id={`child-name-${child.id}`}
                      maxlength="120"
                      bind:value={editingName}
                    />
                    <Button
                      size="compact"
                      onclick={() => saveRename(child.id)}
                      loading={busy}>保存</Button
                    >
                    <Button
                      size="compact"
                      variant="tertiary"
                      onclick={() => (editingChildId = null)}>キャンセル</Button
                    >
                  </div>
                {:else}
                  <h3>{child.display_name}</h3>
                {/if}
                <StatusBadge
                  label={child.is_active ? '在籍中' : '退園済み'}
                  tone={child.is_active ? 'success' : 'neutral'}
                />
              </div>
              <p>
                保護者LINE:
                <strong
                  >{child.guardian_line_user_id ? '連携済み' : '未連携'}</strong
                >
              </p>
              {#if invitationByChild.has(child.id)}
                <p>
                  有効な招待コードあり（期限: {formatDate(
                    invitationByChild.get(child.id)!.expires_at
                  )}）
                </p>
              {/if}
              <div class="people-actions">
                {#if child.is_active}
                  <Button
                    size="compact"
                    variant="secondary"
                    onclick={() => beginRename(child)}>表示名を編集</Button
                  >
                  {#if child.guardian_line_user_id}
                    <Button
                      size="compact"
                      variant="secondary"
                      onclick={() => ask({ kind: 'archive-link', child })}
                      guide="過去のお知らせを確認できるURLを発行します。以前のURLは無効になります。"
                      >保護者用URLを発行</Button
                    >
                    <Button
                      size="compact"
                      variant="danger"
                      onclick={() => ask({ kind: 'unlink', child })}
                      guide="未送信通知や保護者用URLも無効になります。"
                      >LINE連携を解除</Button
                    >
                  {:else}
                    <Button
                      size="compact"
                      variant="secondary"
                      onclick={() =>
                        ask({
                          kind: 'invitation',
                          child,
                          replacing: invitationByChild.has(child.id)
                        })}
                      guide="保護者がLINE連携に使うコードを発行します。一度だけ表示されます。"
                      >招待コードを発行</Button
                    >
                  {/if}
                  <Button
                    size="compact"
                    variant="danger"
                    onclick={() => ask({ kind: 'archive', child })}
                    guide="新しい記録・通知・LINE連携を停止します。過去の履歴は残ります。"
                    >退園処理</Button
                  >
                {:else}
                  <Button
                    size="compact"
                    variant="secondary"
                    onclick={() => ask({ kind: 'restore', child })}
                    guide="在籍中に戻します。以前のLINE連携などは復元されません。"
                    >復園に戻す</Button
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
  tone={confirmation?.kind === 'archive' || confirmation?.kind === 'unlink'
    ? 'danger'
    : 'default'}
  confirmLabel="実行する"
  {busy}
  onConfirm={performConfirmation}
  onCancel={() => (confirmation = null)}
/>
