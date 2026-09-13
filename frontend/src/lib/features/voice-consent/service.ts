import { ApiClient } from '$lib/api';

import type { VoiceConsent } from './types';

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
}
