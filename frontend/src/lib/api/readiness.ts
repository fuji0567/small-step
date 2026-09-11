import { ApiClient } from './client';
import { ApiInvalidResponseError } from './errors';
import type { RuntimeReadiness } from './types';

export async function getRuntimeReadiness(
  client: ApiClient,
  signal?: AbortSignal
): Promise<RuntimeReadiness> {
  const readiness = await client.requestJson<RuntimeReadiness>('/readiness', {
    acceptedStatuses: [503],
    signal
  });
  if (readiness === null) throw new ApiInvalidResponseError();
  return readiness;
}
