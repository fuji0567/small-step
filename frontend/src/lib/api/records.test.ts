import { describe, expect, it, vi } from 'vitest';

import { ApiClient } from './client';
import { createRecordService } from './records';
import type { RecordRead } from './types';

const record: RecordRead = {
  id: 'record-id',
  school_id: 'school-id',
  teacher_id: 'teacher-id',
  child_id: null,
  category: 'growth',
  status: 'pending_review',
  source_event_id: null,
  confidence: 0.9,
  occurred_at: '2026-09-11T00:00:00Z',
  summary: '要約',
  conversation_prompt: null,
  anonymized_context: null,
  reviewed_at: null,
  created_at: '2026-09-11T00:00:00Z',
  updated_at: '2026-09-11T00:00:00Z'
};

describe('RecordService', () => {
  it('一覧を探索せず単体取得endpointを呼ぶ', async () => {
    const fetchMock = vi.fn<typeof fetch>(
      async () =>
        new Response(JSON.stringify(record), {
          headers: { 'content-type': 'application/json' }
        })
    );
    const service = createRecordService(new ApiClient({ fetch: fetchMock }));

    await expect(service.getRecord(' record/id ')).resolves.toEqual(record);

    expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/records/record%2Fid');
    expect(fetchMock.mock.calls[0][0]).not.toContain('?');
  });

  it('空のrecordIdを送信前に拒否する', async () => {
    const fetchMock = vi.fn<typeof fetch>();
    const service = createRecordService(new ApiClient({ fetch: fetchMock }));

    await expect(service.getRecord('   ')).rejects.toThrow(TypeError);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
