import { describe, expect, it, vi } from 'vitest';

import { ApiClient } from '$lib/api';
import { SchoolSettingsService } from './settings-service';

describe('SchoolSettingsService', () => {
  it('園IDをURLエンコードしてdigest timeだけを更新する', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ id: 'school/id' }), {
        headers: { 'content-type': 'application/json' }
      })
    );
    const service = new SchoolSettingsService(
      new ApiClient({ fetch: fetchMock })
    );

    await service.updateDigestTime('school/id', '16:30');

    expect(fetchMock.mock.calls[0][0]).toBe(
      '/api/v1/schools/school%2Fid/digest-time'
    );
    expect(fetchMock.mock.calls[0][1]).toEqual(
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ digest_time: '16:30' })
      })
    );
  });
});
