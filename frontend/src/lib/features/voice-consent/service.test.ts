import { describe, expect, it, vi } from 'vitest';

import { ApiClient } from '$lib/api';
import { VoiceConsentService } from './service';

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    headers: { 'Content-Type': 'application/json' }
  });
}

describe('VoiceConsentService', () => {
  it('本人の同意だけを取得・保存・取消する', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockImplementation(async () => jsonResponse({ is_active: true }));
    const service = new VoiceConsentService(
      new ApiClient({ fetch: fetchMock })
    );

    await service.get();
    await service.grant(30);
    await service.revoke();

    expect(fetchMock.mock.calls.map(([path]) => path)).toEqual([
      '/api/v1/voice-consent/me',
      '/api/v1/voice-consent/me',
      '/api/v1/voice-consent/me/revoke'
    ]);
    expect(fetchMock.mock.calls[1]?.[1]?.body).toBe(
      JSON.stringify({
        accepts_voiceprint_enrollment: true,
        retention_days: 30
      })
    );
  });
});
