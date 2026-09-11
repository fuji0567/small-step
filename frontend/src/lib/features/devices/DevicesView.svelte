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

  import { DevicesService } from './service';
  import type {
    DeviceConfirmation,
    DeviceTeacher,
    EdgeDeviceCredential,
    EdgeDeviceRead
  } from './types';
  import './devices.css';

  type Props = {
    api: ApiClient;
    appController: AppController;
    schoolId: string | null;
    isSchoolAdmin: boolean;
  };

  let { api, appController, schoolId, isSchoolAdmin }: Props = $props();
  const service = $derived(new DevicesService(api));
  let devices = $state.raw<EdgeDeviceRead[]>([]);
  let teachers = $state.raw<DeviceTeacher[]>([]);
  let loading = $state(false);
  let busy = $state(false);
  let errorMessage = $state<string | null>(null);
  let successMessage = $state<string | null>(null);
  let name = $state('');
  let teacherId = $state('');
  let credential = $state<EdgeDeviceCredential | null>(null);
  let confirmation = $state<DeviceConfirmation | null>(null);
  let requestVersion = 0;

  const activeTeachers = $derived(
    teachers.filter((teacher) => teacher.is_active)
  );
  const teacherNames = $derived(
    new Map(teachers.map((teacher) => [teacher.id, teacher.name]))
  );
  const confirmationTitle = $derived(
    confirmation?.kind === 'rotate'
      ? `${confirmation.device.name}の鍵を再発行しますか？`
      : confirmation
        ? `${confirmation.device.name}を無効化しますか？`
        : ''
  );
  const confirmationDescription = $derived(
    confirmation?.kind === 'rotate'
      ? '現在の鍵はすぐ使えなくなります。新しい鍵を端末へ設定してください。'
      : 'この端末からの送信はすぐ拒否されます。再開するときは鍵を再発行してください。'
  );

  function clearCredential(): void {
    credential = null;
  }

  async function load(signal?: AbortSignal): Promise<void> {
    const selectedSchoolId = schoolId;
    const version = ++requestVersion;
    if (!selectedSchoolId || !isSchoolAdmin) {
      devices = [];
      teachers = [];
      return;
    }
    loading = true;
    errorMessage = null;
    try {
      const [nextDevices, nextTeachers] = await Promise.all([
        service.listDevices(selectedSchoolId, signal),
        service.listTeachers(selectedSchoolId, signal)
      ]);
      if (version !== requestVersion) return;
      devices = nextDevices;
      teachers = nextTeachers;
      if (
        !nextTeachers.some(
          (teacher) => teacher.id === teacherId && teacher.is_active
        )
      ) {
        teacherId = nextTeachers.find((teacher) => teacher.is_active)?.id ?? '';
      }
    } catch {
      if (signal?.aborted || version !== requestVersion) return;
      errorMessage = '録音端末と先生の情報を取得できませんでした。';
    } finally {
      if (version === requestVersion) loading = false;
    }
  }

  async function refresh(): Promise<void> {
    await appController.refresh(['edgeDevices']);
  }

  async function createDevice(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    const selectedSchoolId = schoolId;
    const normalizedName = name.trim();
    if (!selectedSchoolId || !teacherId || !normalizedName || busy) return;
    clearCredential();
    busy = true;
    errorMessage = null;
    try {
      credential = await service.create(
        selectedSchoolId,
        teacherId,
        normalizedName
      );
      name = '';
      successMessage =
        '録音端末を登録しました。接続用キーは今だけ表示されています。';
      await refresh();
    } catch {
      errorMessage =
        '録音端末を登録できませんでした。名前の重複や担当先生の状態を確認してください。';
    } finally {
      busy = false;
    }
  }

  async function performConfirmation(): Promise<void> {
    const action = confirmation;
    if (!action || busy) return;
    clearCredential();
    busy = true;
    errorMessage = null;
    try {
      if (action.kind === 'rotate') {
        credential = await service.rotate(action.device.id);
        successMessage = '接続用キーを再発行しました。古い鍵は無効です。';
      } else {
        await service.disable(action.device.id);
        successMessage = '録音端末を無効化しました。';
      }
      await refresh();
    } catch {
      errorMessage = '録音端末の操作を完了できませんでした。';
    } finally {
      busy = false;
      confirmation = null;
    }
  }

  async function copyKey(): Promise<void> {
    if (!credential) return;
    try {
      await navigator.clipboard.writeText(credential.api_key);
      successMessage =
        '接続用キーをコピーしました。端末の設定へ安全に保存してください。';
    } catch {
      errorMessage =
        'キーをコピーできませんでした。表示されたキーを手動でコピーしてください。';
    }
  }

  function formatLastSeen(value: string | null): string {
    if (!value) return '接続履歴なし';
    return new Intl.DateTimeFormat('ja-JP', {
      dateStyle: 'medium',
      timeStyle: 'short'
    }).format(new Date(value));
  }

  $effect(() => {
    const unregister = appController.register('edgeDevices', () => load());
    return unregister;
  });

  $effect(() => {
    const currentSchool = schoolId;
    const currentRole = isSchoolAdmin;
    void currentSchool;
    void currentRole;
    clearCredential();
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  });
</script>

<section class="devices-page" aria-labelledby="devices-heading">
  <header class="devices-heading">
    <h2 id="devices-heading">録音端末</h2>
    <p>園内端末を先生へ割り当て、接続用キーを管理します。</p>
  </header>

  {#if !isSchoolAdmin}
    <Notice tone="warning" title="先生管理者専用です"
      ><p>この画面を利用する権限がありません。</p></Notice
    >
  {:else if !schoolId}
    <Notice tone="warning" title="園を選択してください"
      ><p>園を選択すると録音端末を管理できます。</p></Notice
    >
  {:else}
    {#if activeTeachers.length === 0 && !loading}
      <Notice tone="warning" title="利用中の先生が必要です"
        ><p>先に先生を登録または利用再開してください。</p></Notice
      >
    {/if}
    <form class="devices-form" onsubmit={createDevice}>
      <div class="devices-field">
        <label for="device-name">端末名</label>
        <input id="device-name" maxlength="120" required bind:value={name} />
      </div>
      <div class="devices-field">
        <label for="device-teacher">担当先生</label>
        <select
          id="device-teacher"
          required
          bind:value={teacherId}
          disabled={activeTeachers.length === 0}
        >
          <option value="" disabled>選択してください</option>
          {#each activeTeachers as teacher (teacher.id)}
            <option value={teacher.id}>{teacher.name}先生</option>
          {/each}
        </select>
      </div>
      <Button
        type="submit"
        loading={busy}
        disabled={activeTeachers.length === 0}>端末を登録</Button
      >
    </form>

    {#if successMessage}<Notice tone="success"><p>{successMessage}</p></Notice
      >{/if}
    {#if errorMessage}<Notice tone="error" title="操作できませんでした"
        ><p>{errorMessage}</p></Notice
      >{/if}
    {#if credential}
      <aside class="device-credential" aria-labelledby="device-key-heading">
        <h3 id="device-key-heading">
          {credential.name}の接続用キー（今だけ表示）
        </h3>
        <output>{credential.api_key}</output>
        <Button variant="secondary" onclick={copyKey}>キーをコピー</Button>
      </aside>
    {/if}

    <div class="devices-toolbar">
      <StatusBadge
        label={`${devices.filter((device) => device.is_active).length}台利用中`}
        tone="info"
      />
      <Button variant="secondary" onclick={() => refresh()} disabled={loading}
        >再読み込み</Button
      >
    </div>

    {#if loading}
      <Loading label="録音端末を読み込んでいます" />
    {:else if devices.length === 0}
      <div class="devices-empty">
        <p>登録されている録音端末はありません。</p>
      </div>
    {:else}
      <ul class="devices-list">
        {#each devices as device (device.id)}
          <li>
            <article
              class:devices-card--inactive={!device.is_active}
              class="devices-card"
            >
              <div class="devices-card-heading">
                <div>
                  <h3>{device.name}</h3>
                  <p>
                    担当: {teacherNames.get(device.teacher_id) ??
                      '先生を確認できません'}
                  </p>
                  <p>最終接続: {formatLastSeen(device.last_seen_at)}</p>
                </div>
                <StatusBadge
                  label={device.is_active ? '有効' : '無効'}
                  tone={device.is_active ? 'success' : 'error'}
                />
              </div>
              <div class="devices-actions">
                <Button
                  size="compact"
                  variant="secondary"
                  onclick={() => (confirmation = { kind: 'rotate', device })}
                  >鍵を再発行</Button
                >
                {#if device.is_active}
                  <Button
                    size="compact"
                    variant="danger"
                    onclick={() => (confirmation = { kind: 'disable', device })}
                    >端末を無効化</Button
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
