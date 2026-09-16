import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiClient } from '$lib/api';
import ManualRecordView from './ManualRecordView.svelte';
import RecordDetailView from './RecordDetailView.svelte';
import RecordHistoryView from './RecordHistoryView.svelte';
import ReviewQueueView from './ReviewQueueView.svelte';
import type { RecordChild, RecordRead, RecordTeacher } from './types';

const child: RecordChild = {
  id: 'child-1',
  school_id: 'school-1',
  display_name: '山田 はな',
  guardian_line_user_id: 'line-user',
  is_active: true,
  archived_at: null,
  created_at: '2026-09-11T00:00:00Z'
};

const pendingRecord: RecordRead = {
  id: 'record-1',
  school_id: 'school-1',
  teacher_id: 'teacher-1',
  child_id: child.id,
  category: 'growth',
  status: 'pending_review',
  source_event_id: null,
  confidence: 0.92,
  occurred_at: '2026-09-11T01:00:00Z',
  summary: '積み木を最後まで片付けました。',
  conversation_prompt: 'お家でのお片付けについて',
  anonymized_context: null,
  reviewed_at: null,
  created_at: '2026-09-11T01:00:00Z',
  updated_at: '2026-09-11T01:00:00Z'
};

const teachers: RecordTeacher[] = [
  { id: 'teacher-1', name: '担当先生', is_active: true },
  { id: 'teacher-2', name: '引き継ぎ先生', is_active: true },
  { id: 'teacher-3', name: '利用停止先生', is_active: false }
];

const json = (value: unknown, status = 200): Response =>
  new Response(JSON.stringify(value), {
    status,
    headers: { 'content-type': 'application/json' }
  });

afterEach(() => {
  document.body.innerHTML = '';
  vi.restoreAllMocks();
});

describe('ReviewQueueView', () => {
  it('園児名と日誌ごとのURLを一覧表示する', async () => {
    const fetchMock = vi.fn<typeof fetch>(async (input) => {
      const url = String(input);
      if (url.includes('/children?')) return json([child]);
      if (url.includes('/records?')) return json([pendingRecord]);
      return json({}, 404);
    });

    render(ReviewQueueView, {
      api: new ApiClient({ fetch: fetchMock }),
      schoolId: 'school-1'
    });

    expect(await screen.findByText('山田 はな')).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: '内容を確認する' })
    ).toHaveAttribute('href', '/teacher/review/record-1/');
    expect(screen.getByLabelText('レビュー待ちの日誌1件')).toBeInTheDocument();
    expect(
      screen.getByText('自分の担当分を表示しています')
    ).toBeInTheDocument();
  });
});

describe('RecordDetailView', () => {
  it('音声の一部が処理失敗した記録は承認前の確認を促す', async () => {
    const fetchMock = vi.fn<typeof fetch>(async (input) => {
      if (String(input).includes('/records/record-1')) {
        return json({ ...pendingRecord, audio_processing_incomplete: true });
      }
      return json([child]);
    });

    render(RecordDetailView, {
      api: new ApiClient({ fetch: fetchMock }),
      schoolId: 'school-1',
      recordId: 'record-1',
      onNavigate: vi.fn()
    });

    expect(
      await screen.findByText('一部の音声を処理できませんでした')
    ).toBeInTheDocument();
    expect(screen.getByText(/抜け漏れを確認してから承認/)).toBeInTheDocument();
  });

  it.each([
    [403, 'この日誌を確認する権限がありません。'],
    [404, '指定された日誌は見つかりませんでした。']
  ])('%iを日誌本文なしの日本語エラーで表示する', async (status, message) => {
    const fetchMock = vi.fn<typeof fetch>(async (input) => {
      if (String(input).includes('/records/record-1')) {
        return json({ detail: 'backend detail' }, status);
      }
      return json([child]);
    });

    render(RecordDetailView, {
      api: new ApiClient({ fetch: fetchMock }),
      schoolId: 'school-1',
      recordId: 'record-1',
      onNavigate: vi.fn()
    });

    expect(await screen.findByText(message)).toBeInTheDocument();
    expect(screen.queryByText('backend detail')).not.toBeInTheDocument();
  });

  it('処理済み日誌を参照専用で表示する', async () => {
    const approved = { ...pendingRecord, status: 'approved' as const };
    const fetchMock = vi.fn<typeof fetch>(async (input) =>
      String(input).includes('/children?') ? json([child]) : json(approved)
    );

    render(RecordDetailView, {
      api: new ApiClient({ fetch: fetchMock }),
      schoolId: 'school-1',
      recordId: 'record-1',
      onNavigate: vi.fn()
    });

    expect(
      await screen.findByText('この日誌は処理済みです')
    ).toBeInTheDocument();
    expect(screen.getByDisplayValue(pendingRecord.summary)).toBeDisabled();
    expect(
      screen.queryByRole('button', { name: '承認する' })
    ).not.toBeInTheDocument();
  });

  it('確認をキャンセルでき、承認後は次のレビュー待ちへ移動する', async () => {
    const nextRecord = { ...pendingRecord, id: 'record-2' };
    const onNavigate = vi.fn();
    const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
      const url = String(input);
      if (url.includes('/children?')) return json([child]);
      if (url.includes('/records/record-1/approve')) {
        return json({ ...pendingRecord, status: 'approved' });
      }
      if (url.includes('/records?')) return json([nextRecord]);
      if (url.includes('/records/record-1') && init?.method !== 'POST') {
        return json(pendingRecord);
      }
      return json({}, 404);
    });

    render(RecordDetailView, {
      api: new ApiClient({ fetch: fetchMock }),
      schoolId: 'school-1',
      recordId: 'record-1',
      onNavigate
    });

    await screen.findByDisplayValue(pendingRecord.summary);
    const approve = screen.getByRole('button', { name: '承認する' });
    expect(approve).toHaveAccessibleDescription(
      '編集内容を保存し、保護者へのLINE通知を準備します。'
    );
    await fireEvent.click(approve);
    await fireEvent.click(screen.getByRole('button', { name: 'キャンセル' }));
    expect(
      fetchMock.mock.calls.some(([url]) => String(url).includes('/approve'))
    ).toBe(false);

    await fireEvent.click(screen.getByRole('button', { name: '承認する' }));
    const confirmButtons = screen.getAllByRole('button', { name: '承認する' });
    await fireEvent.click(confirmButtons.at(-1)!);

    await waitFor(() =>
      expect(onNavigate).toHaveBeenCalledWith('/teacher/review/record-2/')
    );
  });

  it('却下後に次の日誌がなければ一覧へ戻る', async () => {
    const onNavigate = vi.fn();
    const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
      const url = String(input);
      if (url.includes('/children?')) return json([child]);
      if (url.includes('/reject') && init?.method === 'POST') {
        return json({ ...pendingRecord, status: 'rejected' });
      }
      if (url.includes('/records?')) return json([]);
      return json(pendingRecord);
    });

    render(RecordDetailView, {
      api: new ApiClient({ fetch: fetchMock }),
      schoolId: 'school-1',
      recordId: 'record-1',
      onNavigate
    });

    await screen.findByDisplayValue(pendingRecord.summary);
    const reject = screen.getByRole('button', { name: '却下する' });
    expect(reject).toHaveAccessibleDescription(
      '確認待ちから外します。保護者には通知されません。'
    );
    await fireEvent.click(reject);
    const rejectButtons = screen.getAllByRole('button', { name: '却下する' });
    await fireEvent.click(rejectButtons.at(-1)!);

    await waitFor(() =>
      expect(onNavigate).toHaveBeenCalledWith('/teacher/review/')
    );
  });

  it('管理者が有効な先生へレビュー待ち日誌を引き継ぐ', async () => {
    const onReassigned = vi.fn();
    const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
      const url = String(input);
      if (url.includes('/children?')) return json([child]);
      if (url.includes('/teachers?')) return json(teachers);
      if (url.includes('/assignee') && init?.method === 'PATCH') {
        return json({ ...pendingRecord, teacher_id: 'teacher-2' });
      }
      return json(pendingRecord);
    });

    render(RecordDetailView, {
      api: new ApiClient({ fetch: fetchMock }),
      schoolId: 'school-1',
      recordId: 'record-1',
      isSchoolAdmin: true,
      onNavigate: vi.fn(),
      onReassigned
    });

    const assignee = await screen.findByLabelText('引き継ぎ先の先生');
    expect(screen.getByText('現在の担当: 担当先生')).toBeInTheDocument();
    expect(
      screen.getByRole('option', { name: '利用停止先生（利用停止中）' })
    ).toBeDisabled();
    await fireEvent.change(assignee, { target: { value: 'teacher-2' } });
    await fireEvent.click(screen.getByRole('button', { name: '担当を変更' }));
    const confirmButtons = screen.getAllByRole('button', {
      name: '担当を変更'
    });
    await fireEvent.click(confirmButtons.at(-1)!);

    expect(
      await screen.findByText('引き継ぎ先生へ担当を引き継ぎました。')
    ).toBeInTheDocument();
    const request = fetchMock.mock.calls.find(([url]) =>
      String(url).includes('/assignee')
    );
    expect(request?.[1]).toEqual(
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ teacher_id: 'teacher-2' })
      })
    );
    expect(onReassigned).toHaveBeenCalledOnce();
  });
});

describe('ManualRecordView', () => {
  it('手入力した日誌を作成して個別URLへ移動する', async () => {
    const onNavigate = vi.fn();
    const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
      const url = String(input);
      if (url.includes('/children?')) return json([child]);
      if (url.endsWith('/records/manual') && init?.method === 'POST') {
        return json(pendingRecord, 201);
      }
      return json({}, 404);
    });

    render(ManualRecordView, {
      api: new ApiClient({ fetch: fetchMock }),
      schoolId: 'school-1',
      currentTeacherId: 'teacher-1',
      onNavigate
    });

    await screen.findByRole('option', { name: '山田 はな' });
    await fireEvent.input(screen.getByLabelText('保護者へ伝える内容'), {
      target: { value: '手入力の日誌です。' }
    });
    const addToReview = screen.getByRole('button', {
      name: 'レビュー待ちに追加'
    });
    expect(addToReview).toHaveAccessibleDescription(
      '保護者には送信せず、先生の確認待ちとして保存します。'
    );
    await fireEvent.click(addToReview);

    await waitFor(() =>
      expect(onNavigate).toHaveBeenCalledWith('/teacher/review/record-1/')
    );
    const createCall = fetchMock.mock.calls.find(([url]) =>
      String(url).endsWith('/records/manual')
    );
    expect(JSON.parse(String(createCall?.[1]?.body))).toEqual(
      expect.objectContaining({
        school_id: 'school-1',
        teacher_id: 'teacher-1',
        child_id: 'child-1',
        summary: '手入力の日誌です。'
      })
    );
  });
});

describe('RecordHistoryView', () => {
  it('履歴を表示し、管理者にだけCSV操作を提供する', async () => {
    const fetchMock = vi.fn<typeof fetch>(async (input) => {
      const url = String(input);
      if (url.includes('/children?')) return json([child]);
      if (url.includes('/teachers?')) return json(teachers);
      return json([pendingRecord]);
    });

    render(RecordHistoryView, {
      api: new ApiClient({ fetch: fetchMock }),
      schoolId: 'school-1',
      isSchoolAdmin: true
    });

    expect(await screen.findByText(pendingRecord.summary)).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'CSVをダウンロード' })
    ).toHaveAccessibleDescription(
      '現在の検索結果を保存します。個人情報を含むため取り扱いに注意してください。'
    );
    expect(
      screen.getByRole('link', { name: '日誌の詳細を開く' })
    ).toHaveAttribute('href', '/teacher/review/record-1/');
  });
});
