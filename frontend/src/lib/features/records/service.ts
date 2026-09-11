import { ApiClient, ApiInvalidResponseError } from '$lib/api';

import type {
  ManualRecordInput,
  RecordChild,
  RecordHistoryFilters,
  RecordRead,
  RecordReviewInput,
  RecordTeacher
} from './types';

function required<T>(value: T | null): T {
  if (value === null) throw new ApiInvalidResponseError();
  return value;
}

function appendOptional(
  params: URLSearchParams,
  key: string,
  value: string | undefined
): void {
  const normalized = value?.trim();
  if (normalized) params.set(key, normalized);
}

export function historySearchParams(
  schoolId: string,
  filters: RecordHistoryFilters,
  includeLimit = true
): URLSearchParams {
  const params = new URLSearchParams({ school_id: schoolId });
  appendOptional(params, 'search', filters.search);
  appendOptional(params, 'child_id', filters.childId);
  appendOptional(params, 'record_status', filters.status || undefined);
  appendOptional(params, 'category', filters.category || undefined);
  appendOptional(params, 'occurred_from', filters.occurredFrom);
  appendOptional(params, 'occurred_to', filters.occurredTo);
  if (includeLimit) params.set('limit', String(filters.limit ?? 100));
  return params;
}

export class RecordsService {
  constructor(private readonly client: ApiClient) {}

  async listChildren(
    schoolId: string,
    signal?: AbortSignal
  ): Promise<RecordChild[]> {
    const params = new URLSearchParams({
      school_id: schoolId,
      include_archived: 'true'
    });
    return required(
      await this.client.requestJson<RecordChild[]>(`children?${params}`, {
        signal
      })
    );
  }

  async listTeachers(
    schoolId: string,
    signal?: AbortSignal
  ): Promise<RecordTeacher[]> {
    const params = new URLSearchParams({ school_id: schoolId });
    return required(
      await this.client.requestJson<RecordTeacher[]>(`teachers?${params}`, {
        signal
      })
    );
  }

  async listPending(
    schoolId: string,
    signal?: AbortSignal
  ): Promise<RecordRead[]> {
    const params = new URLSearchParams({
      school_id: schoolId,
      record_status: 'pending_review'
    });
    return required(
      await this.client.requestJson<RecordRead[]>(`records?${params}`, {
        signal
      })
    );
  }

  async get(recordId: string, signal?: AbortSignal): Promise<RecordRead> {
    return required(
      await this.client.requestJson<RecordRead>(
        `records/${encodeURIComponent(recordId)}`,
        { signal }
      )
    );
  }

  async approve(
    recordId: string,
    input: RecordReviewInput
  ): Promise<RecordRead> {
    return required(
      await this.client.requestJson<RecordRead>(
        `records/${encodeURIComponent(recordId)}/approve`,
        { method: 'POST', json: input }
      )
    );
  }

  async reject(recordId: string): Promise<RecordRead> {
    return required(
      await this.client.requestJson<RecordRead>(
        `records/${encodeURIComponent(recordId)}/reject`,
        { method: 'POST' }
      )
    );
  }

  async createManual(input: ManualRecordInput): Promise<RecordRead> {
    return required(
      await this.client.requestJson<RecordRead>('records/manual', {
        method: 'POST',
        json: input
      })
    );
  }

  async listHistory(
    schoolId: string,
    filters: RecordHistoryFilters,
    signal?: AbortSignal
  ): Promise<RecordRead[]> {
    return required(
      await this.client.requestJson<RecordRead[]>(
        `records?${historySearchParams(schoolId, filters)}`,
        { signal }
      )
    );
  }

  async exportHistory(
    schoolId: string,
    filters: RecordHistoryFilters
  ): Promise<Blob> {
    return required(
      await this.client.requestBlob(
        `records/export.csv?${historySearchParams(schoolId, filters, false)}`,
        { headers: { Accept: 'text/csv' } }
      )
    );
  }
}
