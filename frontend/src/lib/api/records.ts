import { ApiClient } from './client';
import { ApiInvalidResponseError } from './errors';
import type { RecordRead } from './types';

export interface RecordService {
  getRecord(recordId: string, signal?: AbortSignal): Promise<RecordRead>;
}

export function createRecordService(client: ApiClient): RecordService {
  return {
    async getRecord(
      recordId: string,
      signal?: AbortSignal
    ): Promise<RecordRead> {
      const normalizedId = recordId.trim();
      if (!normalizedId) throw new TypeError('recordId is required');
      const record = await client.requestJson<RecordRead>(
        `/records/${encodeURIComponent(normalizedId)}`,
        { signal }
      );
      if (record === null) throw new ApiInvalidResponseError();
      return record;
    }
  };
}
