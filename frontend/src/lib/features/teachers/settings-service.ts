import { ApiClient, ApiInvalidResponseError } from '$lib/api';
import type { SchoolSummary } from '$lib/state';

export class SchoolSettingsService {
  constructor(private readonly client: ApiClient) {}

  async updateTrialMode(
    schoolId: string,
    trialMode: boolean,
    deliveryConfirmed: boolean
  ): Promise<SchoolSummary> {
    const school = await this.client.requestJson<SchoolSummary>(
      `schools/${encodeURIComponent(schoolId)}/trial-mode`,
      {
        method: 'PATCH',
        json: { trial_mode: trialMode, delivery_confirmed: deliveryConfirmed }
      }
    );
    if (school === null) throw new ApiInvalidResponseError();
    return school;
  }

  async updateDigestTime(
    schoolId: string,
    digestTime: string
  ): Promise<SchoolSummary> {
    const school = await this.client.requestJson<SchoolSummary>(
      `schools/${encodeURIComponent(schoolId)}/digest-time`,
      { method: 'PATCH', json: { digest_time: digestTime } }
    );
    if (school === null) throw new ApiInvalidResponseError();
    return school;
  }
}
