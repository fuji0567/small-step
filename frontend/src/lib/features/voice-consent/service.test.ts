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
        allows_recorder_identification: false,
        retention_days: 30
      })
    );
  });

  it('録音からの照合は明示的に選んだ場合だけ許可する', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse(null));
    const service = new VoiceConsentService(
      new ApiClient({ fetch: fetchMock })
    );
    await service.grant(30, true);
    expect(
      JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))
    ).toMatchObject({
      allows_recorder_identification: true
    });
  });

  it('声紋音声をFormDataで送信し、本人のジョブだけを確認する', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockImplementation(async () => jsonResponse({ status: 'queued' }));
    const service = new VoiceConsentService(
      new ApiClient({ fetch: fetchMock })
    );
    const audios = [1, 2, 3].map(
      (index) =>
        new File(['audio'], `teacher-${index}.wav`, { type: 'audio/wav' })
    );

    await service.getVoiceprint();
    await service.enroll(audios);
    await service.verify(audios[0]);
    await service.getJob('job/id');
    await service.deleteVoiceprint();

    expect(fetchMock.mock.calls.map(([path]) => path)).toEqual([
      '/api/v1/voiceprint/me',
      '/api/v1/voiceprint/me/enroll',
      '/api/v1/voiceprint/me/verify',
      '/api/v1/voiceprint-jobs/job/id',
      '/api/v1/voiceprint/me'
    ]);
    expect(fetchMock.mock.calls[1]?.[1]?.body).toBeInstanceOf(FormData);
    expect(fetchMock.mock.calls[2]?.[1]?.body).toBeInstanceOf(FormData);
    expect(
      (fetchMock.mock.calls[1]?.[1]?.body as FormData).getAll('audio')
    ).toHaveLength(3);
    expect(
      (fetchMock.mock.calls[2]?.[1]?.body as FormData).getAll('audio')
    ).toHaveLength(1);
    expect(fetchMock.mock.calls[4]?.[1]?.method).toBe('DELETE');
  });
});
