import { describe, expect, it, vi } from 'vitest';

import { ApiClient } from '$lib/api';
import { historySearchParams, RecordsService } from './service';
import type { RecordHistoryFilters } from './types';

const response = (value: unknown): Response =>
  new Response(JSON.stringify(value), {
    headers: { 'content-type': 'application/json' }
  });

describe('RecordsService', () => {
  it('レビュー一覧に園IDとpending_reviewを付け、退園済み園児も取得する', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(response([]))
      .mockResolvedValueOnce(response([]));
    const service = new RecordsService(new ApiClient({ fetch: fetchMock }));

    await service.listChildren('school/id');
    await service.listPending('school/id');

    expect(fetchMock.mock.calls[0][0]).toBe(
      '/api/v1/children?school_id=school%2Fid&include_archived=true'
    );
    expect(fetchMock.mock.calls[1][0]).toBe(
      '/api/v1/records?school_id=school%2Fid&record_status=pending_review'
    );
  });

  it('承認時の編集内容をJSONで送信する', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(response({}));
    const service = new RecordsService(new ApiClient({ fetch: fetchMock }));
    const input = {
      child_id: 'child-id',
      summary: '保護者へ伝える内容',
      conversation_prompt: '会話のきっかけ'
    };

    await service.approve('record/id', input);

    expect(fetchMock.mock.calls[0][0]).toBe(
      '/api/v1/records/record%2Fid/approve'
    );
    expect(fetchMock.mock.calls[0][1]).toEqual(
      expect.objectContaining({ method: 'POST', body: JSON.stringify(input) })
    );
  });

  it('担当変更を専用URLへPATCHする', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(response({}));
    const service = new RecordsService(new ApiClient({ fetch: fetchMock }));

    await service.reassign('record/id', { teacher_id: 'teacher-2' });

    expect(fetchMock.mock.calls[0][0]).toBe(
      '/api/v1/records/record%2Fid/assignee'
    );
    expect(fetchMock.mock.calls[0][1]).toEqual(
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ teacher_id: 'teacher-2' })
      })
    );
  });

  it('履歴検索の空条件を除外し、CSVではlimitを送らない', () => {
    const filters: RecordHistoryFilters = {
      search: ' 成長 ',
      childId: '',
      status: 'approved' as const,
      category: '',
      occurredFrom: '2026-09-01T00:00:00.000Z',
      limit: 50
    };

    expect(historySearchParams('school-id', filters).toString()).toBe(
      'school_id=school-id&search=%E6%88%90%E9%95%B7&record_status=approved&occurred_from=2026-09-01T00%3A00%3A00.000Z&limit=50'
    );
    expect(historySearchParams('school-id', filters, false).has('limit')).toBe(
      false
    );
  });
});
