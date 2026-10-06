import { describe, expect, it, vi } from 'vitest';

import { ApiClient } from '$lib/api';

import { ClassDeliveryService } from './service';

describe('ClassDeliveryService', () => {
  it('encodes a class id when refreshing an unapproved candidate batch', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: 'batch', entries: [] }), {
        headers: { 'Content-Type': 'application/json' }
      })
    );
    const service = new ClassDeliveryService(
      new ApiClient({ fetch: fetchMock })
    );

    await service.refreshGrowth('batch/id');

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('growth-delivery-batches/batch%2Fid/refresh'),
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('sends the teacher-confirmed record selection to the approval endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: 'batch', entries: [] }), {
        headers: { 'Content-Type': 'application/json' }
      })
    );
    const service = new ClassDeliveryService(
      new ApiClient({ fetch: fetchMock })
    );

    await service.approveGrowth('batch', ['record-1']);

    const [, request] = fetchMock.mock.calls[0];
    expect(JSON.parse(String(request?.body))).toEqual({
      selected_record_ids: ['record-1'],
      teacher_confirmed: true
    });
  });
});
