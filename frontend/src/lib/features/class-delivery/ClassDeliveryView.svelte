<script lang="ts">
  import type { ApiClient } from '$lib/api';
  import { Button, Loading, Notice } from '$lib/components';
  import { onMount } from 'svelte';

  import { ClassDeliveryService } from './service';
  import type {
    ClassChild,
    Classroom,
    ClassNewsletter,
    GrowthDeliveryBatch
  } from './types';
  import './class-delivery.css';

  type Props = {
    api: ApiClient;
    schoolId: string | null;
    schoolTimezone: string;
    schoolTrialMode: boolean;
    isSchoolAdmin: boolean;
  };

  let { api, schoolId, schoolTimezone, schoolTrialMode, isSchoolAdmin }: Props =
    $props();
  const service = $derived(new ClassDeliveryService(api));
  let classrooms = $state.raw<Classroom[]>([]);
  let children = $state.raw<ClassChild[]>([]);
  let selectedClassId = $state('');
  let selectedDate = $state('');
  let newsletter = $state<ClassNewsletter | null>(null);
  let batch = $state<GrowthDeliveryBatch | null>(null);
  let selectedRecords = $state<string[]>([]);
  let newsletterBody = $state('');
  let newClassName = $state('');
  let loading = $state(true);
  let busy = $state(false);
  let errorMessage = $state<string | null>(null);
  let noticeMessage = $state<string | null>(null);

  const selectedClass = $derived(
    classrooms.find((item) => item.id === selectedClassId) ?? null
  );
  const unassignedChildren = $derived(
    children.filter((child) => child.is_active && !child.classroom_id)
  );
  const childrenInClass = $derived(
    children.filter(
      (child) => child.is_active && child.classroom_id === selectedClassId
    )
  );

  function localToday(timezone: string): string {
    try {
      return new Intl.DateTimeFormat('en-CA', {
        timeZone: timezone,
        year: 'numeric',
        month: '2-digit',
        day: '2-digit'
      }).format(new Date());
    } catch {
      return new Date().toISOString().slice(0, 10);
    }
  }

  async function load(): Promise<void> {
    if (!selectedDate) selectedDate = localToday(schoolTimezone);
    if (!schoolId) {
      classrooms = [];
      children = [];
      loading = false;
      return;
    }
    loading = true;
    errorMessage = null;
    try {
      const [nextClasses, nextChildren] = await Promise.all([
        service.listClasses(schoolId),
        service.listChildren(schoolId)
      ]);
      classrooms = nextClasses;
      children = nextChildren;
      if (!nextClasses.some((item) => item.id === selectedClassId)) {
        selectedClassId = nextClasses[0]?.id ?? '';
      }
      await loadDaily();
    } catch {
      errorMessage = 'クラス情報を読み込めませんでした。';
    } finally {
      loading = false;
    }
  }

  async function loadDaily(): Promise<void> {
    newsletter = null;
    batch = null;
    selectedRecords = [];
    newsletterBody = '';
    if (!schoolId || !selectedClassId) return;
    try {
      const existing = await service.newsletters(
        schoolId,
        selectedClassId,
        selectedDate
      );
      newsletter = existing[0] ?? null;
      newsletterBody = newsletter?.body ?? '';
    } catch {
      errorMessage = '当日の配信状況を読み込めませんでした。';
    }
  }

  onMount(() => {
    void load();
  });

  async function createClass(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    if (!schoolId || !newClassName.trim() || busy) return;
    busy = true;
    errorMessage = null;
    try {
      const created = await service.createClass(schoolId, newClassName.trim());
      newClassName = '';
      selectedClassId = created.id;
      noticeMessage = 'クラスを作成しました。新しい配信方式は無効のままです。';
      await load();
    } catch {
      errorMessage =
        'クラスを作成できませんでした。名前が重複していないか確認してください。';
    } finally {
      busy = false;
    }
  }

  async function saveClassSettings(): Promise<void> {
    if (!selectedClass || busy) return;
    busy = true;
    errorMessage = null;
    try {
      const saved = await service.updateClass(selectedClass);
      classrooms = classrooms.map((item) =>
        item.id === saved.id ? saved : item
      );
      noticeMessage = 'クラスの配信設定を保存しました。';
    } catch {
      errorMessage = 'クラス設定を保存できませんでした。';
    } finally {
      busy = false;
    }
  }

  function updateSelectedClass(patch: Partial<Classroom>): void {
    if (!selectedClass) return;
    classrooms = classrooms.map((item) =>
      item.id === selectedClass.id ? { ...item, ...patch } : item
    );
  }

  async function assignChild(
    childId: string,
    classroomId: string
  ): Promise<void> {
    busy = true;
    errorMessage = null;
    try {
      const updated = await service.assignChild(childId, classroomId || null);
      children = children.map((child) =>
        child.id === updated.id
          ? { ...child, classroom_id: updated.classroom_id }
          : child
      );
      noticeMessage = '園児のクラス所属を更新しました。';
    } catch {
      errorMessage =
        'クラス所属を更新できませんでした。園児とクラスが同じ園か確認してください。';
    } finally {
      busy = false;
    }
  }

  async function saveNewsletter(): Promise<void> {
    if (!selectedClassId || !newsletterBody.trim() || busy) return;
    busy = true;
    errorMessage = null;
    try {
      newsletter =
        newsletter?.status === 'draft'
          ? await service.editNewsletter(newsletter.id, newsletterBody)
          : await service.saveNewsletter(
              selectedClassId,
              selectedDate,
              newsletterBody
            );
      newsletterBody = newsletter.body;
      noticeMessage = 'クラスのお便りを下書き保存しました。';
    } catch {
      errorMessage =
        '下書きを保存できませんでした。同じ日のお便りが承認済みでないか確認してください。';
    } finally {
      busy = false;
    }
  }

  async function approveNewsletter(): Promise<void> {
    if (!newsletter || busy) return;
    busy = true;
    errorMessage = null;
    try {
      newsletter = await service.approveNewsletter(newsletter.id);
      noticeMessage = schoolTrialMode
        ? '確認しました。試用中のため保護者には配信されません。'
        : 'クラスのお便りを承認しました。設定時刻に配信対象となります。';
    } catch {
      errorMessage =
        '承認できませんでした。クラス設定、配信日、本文を確認してください。';
    } finally {
      busy = false;
    }
  }

  async function retryNewsletter(): Promise<void> {
    if (!newsletter || busy) return;
    busy = true;
    errorMessage = null;
    try {
      newsletter = await service.retryNewsletter(newsletter.id);
      noticeMessage =
        '失敗した宛先だけを再送待ちにしました。受付済みの宛先は再送しません。';
    } catch {
      errorMessage =
        '失敗分を再送待ちにできませんでした。クラスの状態を確認してください。';
    } finally {
      busy = false;
    }
  }

  async function cancelNewsletter(): Promise<void> {
    if (!newsletter || busy) return;
    if (!globalThis.confirm('未送信のクラスお便りを取り消しますか？')) return;
    busy = true;
    errorMessage = null;
    try {
      newsletter = await service.cancelNewsletter(newsletter.id);
      noticeMessage = '未送信の宛先への配信を取り消しました。';
    } catch {
      errorMessage = 'クラスお便りを取り消せませんでした。';
    } finally {
      busy = false;
    }
  }

  async function proposeGrowth(): Promise<void> {
    if (!selectedClassId || busy) return;
    busy = true;
    errorMessage = null;
    try {
      batch = await service.proposeGrowth(selectedClassId, selectedDate);
      selectedRecords = batch.entries
        .filter((entry) => entry.selected)
        .map((entry) => entry.record_id);
      noticeMessage =
        batch.entries.length === 0
          ? '今日の候補はありません。配信枠を埋めるための記録は作りません。'
          : '候補を公平な順序で提案しました。内容と宛先を確認してください。';
    } catch {
      errorMessage =
        '個人成長候補を準備できませんでした。クラス設定と対象日を確認してください。';
    } finally {
      busy = false;
    }
  }

  async function refreshGrowth(): Promise<void> {
    if (!batch || batch.status !== 'draft' || busy) return;
    if (
      !globalThis.confirm(
        '候補を最新の承認済み記録で作り直します。現在の選択はリセットされます。続けますか？'
      )
    )
      return;
    busy = true;
    errorMessage = null;
    try {
      batch = await service.refreshGrowth(batch.id);
      selectedRecords = batch.entries
        .filter((entry) => entry.selected)
        .map((entry) => entry.record_id);
      noticeMessage =
        '最新の承認済み記録で候補を更新しました。内容を再確認してください。';
    } catch {
      errorMessage = '候補を更新できませんでした。配信状態を確認してください。';
    } finally {
      busy = false;
    }
  }

  function toggleRecord(recordId: string, checked: boolean): void {
    if (checked) selectedRecords = [...selectedRecords, recordId];
    else selectedRecords = selectedRecords.filter((id) => id !== recordId);
  }

  async function approveGrowth(): Promise<void> {
    if (!batch || busy) return;
    busy = true;
    errorMessage = null;
    try {
      batch = await service.approveGrowth(batch.id, selectedRecords);
      noticeMessage = schoolTrialMode
        ? '試用記録を確認しました。保護者には配信されません。'
        : '個人配信対象を承認しました。設定時刻に配信対象となります。';
    } catch {
      errorMessage =
        '承認できませんでした。日次上限、候補の在籍・所属・LINE連携を確認してください。';
    } finally {
      busy = false;
    }
  }

  async function cancelGrowth(): Promise<void> {
    if (!batch || busy) return;
    if (!globalThis.confirm('未送信の個人成長お便りを取り消しますか？')) return;
    busy = true;
    errorMessage = null;
    try {
      batch = await service.cancelGrowth(batch.id);
      noticeMessage = '未送信の個人成長お便りを取り消しました。';
    } catch {
      errorMessage = '個人成長お便りを取り消せませんでした。';
    } finally {
      busy = false;
    }
  }
</script>

<main class="class-delivery">
  <header class="class-delivery__heading">
    <p class="class-delivery__eyebrow">クラスのお便りと個人成長</p>
    <h1>今日の配信を確認</h1>
    <p>
      毎日の対象日は先生が確認した日です。候補がなければ、個人配信は0件で構いません。
    </p>
  </header>

  {#if errorMessage}<Notice tone="error" title="処理できませんでした"
      ><p>{errorMessage}</p></Notice
    >{/if}
  {#if noticeMessage}<Notice tone="success"><p>{noticeMessage}</p></Notice>{/if}
  {#if schoolTrialMode}
    <Notice tone="warning" title="試用モード"
      ><p>
        この園では保護者へのクラス・個人配信を行いません。試用解除後に過去分を遡って送ることもありません。
      </p></Notice
    >
  {/if}
  {#if loading}<Loading label="クラスと配信状況を読み込んでいます" />{:else}
    {#if isSchoolAdmin}
      <section
        class="class-delivery__card"
        aria-labelledby="class-settings-heading"
      >
        <div>
          <h2 id="class-settings-heading">クラスと配信設定</h2>
          <p>園児の所属は推測せず、管理者が登録します。</p>
        </div>
        <form class="class-delivery__create" onsubmit={createClass}>
          <label for="new-class-name">クラス名</label>
          <input
            id="new-class-name"
            bind:value={newClassName}
            maxlength="120"
            required
          />
          <Button type="submit" disabled={busy}>クラスを追加</Button>
        </form>
        {#if classrooms.length}
          <div class="class-delivery__settings">
            <label for="settings-class">設定するクラス</label>
            <select
              id="settings-class"
              bind:value={selectedClassId}
              onchange={loadDaily}
            >
              {#each classrooms as classroom (classroom.id)}<option
                  value={classroom.id}>{classroom.name}</option
                >{/each}
            </select>
            {#if selectedClass}
              <label class="class-delivery__check"
                ><input
                  type="checkbox"
                  checked={selectedClass.delivery_enabled}
                  onchange={(event) =>
                    updateSelectedClass({
                      delivery_enabled: event.currentTarget.checked
                    })}
                />このクラスで新しい配信方式を有効にする</label
              >
              <label for="daily-limit">個人の成長お便りの1日上限</label>
              <select
                id="daily-limit"
                value={String(selectedClass.daily_growth_limit)}
                onchange={(event) =>
                  updateSelectedClass({
                    daily_growth_limit: Number(event.currentTarget.value)
                  })}
              >
                <option value={1}>1人</option><option value={2}>2人</option>
              </select>
              <Button
                variant="secondary"
                onclick={saveClassSettings}
                disabled={busy}>設定を保存</Button
              >
            {/if}
          </div>
          {#if selectedClass}
            <div class="class-delivery__roster">
              <h3>{selectedClass.name}の園児所属</h3>
              {#each childrenInClass as child (child.id)}
                <label class="class-delivery__roster-row"
                  >{child.display_name}
                  <select
                    aria-label={`${child.display_name}さんのクラス`}
                    value={child.classroom_id ?? ''}
                    onchange={(event) =>
                      assignChild(child.id, event.currentTarget.value)}
                    disabled={busy}
                  >
                    <option value="">未所属</option
                    >{#each classrooms as item (item.id)}<option value={item.id}
                        >{item.name}</option
                      >{/each}
                  </select>
                </label>
              {/each}
              {#each unassignedChildren as child (child.id)}
                <label class="class-delivery__roster-row"
                  >{child.display_name}
                  <select
                    aria-label={`${child.display_name}さんのクラス`}
                    value=""
                    onchange={(event) =>
                      assignChild(child.id, event.currentTarget.value)}
                    disabled={busy}
                  >
                    <option value="">未所属</option
                    >{#each classrooms as item (item.id)}<option value={item.id}
                        >{item.name}</option
                      >{/each}
                  </select>
                </label>
              {/each}
              {#if childrenInClass.length === 0 && unassignedChildren.length === 0}<p
                >
                  在籍中の園児はいません。
                </p>{/if}
            </div>
          {/if}
        {/if}
      </section>
    {/if}

    <section class="class-delivery__card" aria-labelledby="daily-heading">
      <div>
        <h2 id="daily-heading">先生が確認する当日の配信</h2>
        <p>
          承認前は配信されません。送信受付は、保護者が読んだことを意味しません。
        </p>
      </div>
      {#if classrooms.length === 0}
        <p>クラスがまだありません。園管理者にクラス作成を依頼してください。</p>
      {:else}
        <div class="class-delivery__daily-controls">
          <label for="delivery-class">クラス</label>
          <select
            id="delivery-class"
            bind:value={selectedClassId}
            onchange={loadDaily}
          >
            {#each classrooms as classroom (classroom.id)}<option
                value={classroom.id}>{classroom.name}</option
              >{/each}
          </select>
          <label for="delivery-date">対象日</label><input
            id="delivery-date"
            type="date"
            bind:value={selectedDate}
            onchange={loadDaily}
          />
        </div>
        {#if selectedClass && !selectedClass.delivery_enabled}
          <Notice tone="info"
            ><p>
              このクラスの新しい配信方式は無効です。既存の個人通知の動作は変更されません。
            </p></Notice
          >
        {:else}
          <div class="class-delivery__section">
            <h3>クラスのお便り</h3>
            <p>
              個人名、個別の怪我・トラブル、家庭事情を含めず、クラス全体の様子を入力します。
            </p>
            <label for="class-newsletter-body">本文</label>
            <textarea
              id="class-newsletter-body"
              bind:value={newsletterBody}
              maxlength="3000"
              rows="6"
              disabled={newsletter !== null && newsletter.status !== 'draft'}
            ></textarea>
            {#if newsletter}
              <p>
                状態：{newsletter.status === 'draft'
                  ? '下書き'
                  : newsletter.status === 'approved'
                    ? '承認済み'
                    : newsletter.status === 'cancelled'
                      ? '取消'
                      : newsletter.status}
              </p>
              {#if newsletter.status === 'approved'}<p>
                  宛先：{newsletter.recipient_count}件 / LINE受付：{newsletter.sent_count}件
                  / 失敗：{newsletter.failed_count}件
                </p>{/if}
            {/if}
            <div class="class-delivery__actions">
              {#if !newsletter || newsletter.status === 'draft'}<Button
                  variant="secondary"
                  onclick={saveNewsletter}
                  disabled={busy || !newsletterBody.trim()}>下書き保存</Button
                >{/if}
              {#if newsletter?.status === 'draft'}<Button
                  onclick={approveNewsletter}
                  disabled={busy}>本文と宛先を確認して承認</Button
                >{/if}
              {#if newsletter?.status === 'approved' && newsletter.failed_count > 0}<Button
                  variant="secondary"
                  onclick={retryNewsletter}
                  disabled={busy}>失敗した宛先だけ再送</Button
                >{/if}
              {#if newsletter && ['draft', 'approved'].includes(newsletter.status)}<Button
                  variant="secondary"
                  onclick={cancelNewsletter}
                  disabled={busy}>未送信分を取り消す</Button
                >{/if}
            </div>
          </div>

          <div class="class-delivery__section">
            <h3>個人の成長のお便り</h3>
            <p>
              1日上限：{selectedClass?.daily_growth_limit ??
                1}人。配信回数が少なく、前回配信が古い園児を優先します。
            </p>
            {#if !batch}<Button
                onclick={proposeGrowth}
                disabled={busy || !selectedClass}>今日の候補を準備</Button
              >
            {:else}
              <p>選択数：{selectedRecords.length}/{batch.daily_limit}人</p>
              {#if isSchoolAdmin && batch.status === 'draft'}<Button
                  variant="secondary"
                  onclick={refreshGrowth}
                  disabled={busy}>候補を最新状態に更新</Button
                >{/if}
              {#if batch.entries.length === 0}<Notice tone="info"
                  ><p>
                    候補はありません。枠を埋めるために記録を作ることはありません。
                  </p></Notice
                >
              {:else}
                <fieldset
                  class="class-delivery__candidates"
                  disabled={batch.status !== 'draft' ||
                    busy ||
                    batch.requires_admin_review}
                >
                  <legend>個人配信の候補</legend>
                  {#each batch.entries as entry (entry.record_id)}
                    <label class="class-delivery__candidate">
                      <input
                        type="checkbox"
                        checked={selectedRecords.includes(entry.record_id)}
                        onchange={(event) =>
                          toggleRecord(
                            entry.record_id,
                            event.currentTarget.checked
                          )}
                        disabled={!selectedRecords.includes(entry.record_id) &&
                          selectedRecords.length >= batch.daily_limit}
                      />
                      <span
                        ><strong>{entry.child_name}さん</strong><span
                          >{entry.summary}</span
                        ><small
                          >これまでのLINE受付：{entry.accepted_delivery_count}回{entry.last_sent_at
                            ? `・前回 ${new Intl.DateTimeFormat('ja-JP').format(new Date(entry.last_sent_at))}`
                            : '・配信履歴なし'}</small
                        ></span
                      >
                    </label>
                  {/each}
                </fieldset>
              {/if}
              {#if batch.requires_admin_review}<Notice tone="warning"
                  ><p>
                    この日の候補には、あなたの記録閲覧権限外の記録が含まれます。内容を表示せずに選択状態を変えないため、園管理者が全体を確認・承認してください。
                  </p></Notice
                >{/if}
              {#if batch.candidates_without_guardian_link > 0}<p>
                  保護者LINE未連携のため対象外：{batch.candidates_without_guardian_link}人
                </p>{/if}
              {#if batch.status === 'draft'}<Button
                  onclick={approveGrowth}
                  disabled={busy || batch.requires_admin_review}
                  >選んだ内容を確認して承認</Button
                >
              {:else if batch.status === 'approved'}<p>
                  個人配信は承認済みです。配信数はLINEの受付結果で確定します。
                </p>
                <Button
                  variant="secondary"
                  onclick={cancelGrowth}
                  disabled={busy || batch.requires_admin_review}
                  >未送信分を取り消す</Button
                >
              {:else}<p>
                  この日の個人配信は{batch.status === 'cancelled'
                    ? '取り消されています'
                    : batch.status}。
                </p>{/if}
            {/if}
          </div>
        {/if}
      {/if}
    </section>
  {/if}
</main>
