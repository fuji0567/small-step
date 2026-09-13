import {
  ApiClient,
  ApiInvalidResponseError,
  getRuntimeReadiness,
  type RuntimeReadiness
} from '$lib/api';

import type { AuditEvent, AuditFilters, CloudAudioJob } from './types';

function dateFilterToIso(value: string, endOfDay = false): string | null {
  if (!value) return null;
  const date = new Date(
    `${value}T${endOfDay ? '23:59:59.999' : '00:00:00.000'}`
  );
  return Number.isFinite(date.getTime()) ? date.toISOString() : null;
}

export function auditParams(
  schoolId: string,
  filters: AuditFilters,
  includeLimit = true
): URLSearchParams {
  const params = new URLSearchParams({ school_id: schoolId });
  if (includeLimit) params.set('limit', '100');
  if (filters.action) params.set('action', filters.action);
  const occurredFrom = dateFilterToIso(filters.occurredFrom);
  const occurredTo = dateFilterToIso(filters.occurredTo, true);
  if (occurredFrom) params.set('occurred_from', occurredFrom);
  if (occurredTo) params.set('occurred_to', occurredTo);
  return params;
}

export class OperationsService {
  constructor(private readonly api: ApiClient) {}

  async listAudioJobs(
    schoolId: string,
    signal?: AbortSignal
  ): Promise<CloudAudioJob[]> {
    const value = await this.api.requestJson<CloudAudioJob[]>(
      `/audio-jobs?${new URLSearchParams({ school_id: schoolId })}`,
      { signal }
    );
    if (!Array.isArray(value)) throw new ApiInvalidResponseError();
    return value;
  }

  readiness(signal?: AbortSignal): Promise<RuntimeReadiness> {
    return getRuntimeReadiness(this.api, signal);
  }

  async listAuditEvents(
    schoolId: string,
    filters: AuditFilters,
    signal?: AbortSignal
  ): Promise<AuditEvent[]> {
    const value = await this.api.requestJson<AuditEvent[]>(
      `/audit-events?${auditParams(schoolId, filters)}`,
      { signal }
    );
    if (!Array.isArray(value)) throw new ApiInvalidResponseError();
    return value;
  }

  async exportAuditEvents(
    schoolId: string,
    filters: AuditFilters
  ): Promise<Blob> {
    const value = await this.api.requestBlob(
      `/audit-events/export.csv?${auditParams(schoolId, filters, false)}`,
      { headers: { Accept: 'text/csv' } }
    );
    if (value === null) throw new ApiInvalidResponseError();
    return value;
  }
}
