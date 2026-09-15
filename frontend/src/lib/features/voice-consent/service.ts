import { ApiClient } from '$lib/api';

import type { VoiceConsent, Voiceprint, VoiceprintJob } from './types';

export class VoiceConsentService {
  constructor(private readonly api: ApiClient) {}

  get(signal?: AbortSignal): Promise<VoiceConsent | null> {
    return this.api.requestJson<VoiceConsent>('/voice-consent/me', { signal });
  }

  grant(retentionDays: number): Promise<VoiceConsent | null> {
    return this.api.requestJson('/voice-consent/me', {
      method: 'POST',
      json: {
        accepts_voiceprint_enrollment: true,
        retention_days: retentionDays
      }
    });
  }

  revoke(): Promise<VoiceConsent | null> {
    return this.api.requestJson('/voice-consent/me/revoke', { method: 'POST' });
  }

  getVoiceprint(signal?: AbortSignal): Promise<Voiceprint | null> {
    return this.api.requestJson<Voiceprint>('/voiceprint/me', { signal });
  }

  enroll(audio: File): Promise<VoiceprintJob | null> {
    return this.submitAudio('/voiceprint/me/enroll', audio);
  }

  verify(audio: File): Promise<VoiceprintJob | null> {
    return this.submitAudio('/voiceprint/me/verify', audio);
  }

  getJob(jobId: string): Promise<VoiceprintJob | null> {
    return this.api.requestJson<VoiceprintJob>(`/voiceprint-jobs/${jobId}`);
  }

  async deleteVoiceprint(): Promise<void> {
    await this.api.requestJson('/voiceprint/me', { method: 'DELETE' });
  }

  private submitAudio(
    path: string,
    audio: File
  ): Promise<VoiceprintJob | null> {
    const body = new FormData();
    body.append('audio', audio);
    return this.api.requestJson<VoiceprintJob>(path, { method: 'POST', body });
  }
}
