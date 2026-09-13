import {
  ApiClient,
  ApiHttpError,
  ApiInvalidResponseError,
  ApiRequestCancelledError
} from '$lib/api';

import { GUARDIAN_ARCHIVE_TOKEN_STORAGE_KEY } from './token';
import type {
  GuardianArchive,
  GuardianArchiveLoadResult,
  GuardianArchiveNotification
} from './types';

type GuardianStorage = Pick<Storage, 'removeItem'>;

function isString(value: unknown): value is string {
  return typeof value === 'string';
}

function isNotification(value: unknown): value is GuardianArchiveNotification {
  if (typeof value !== 'object' || value === null) return false;
  const item = value as Record<string, unknown>;
  return (
    isString(item.delivered_at) &&
    (item.category === 'growth' || item.category === 'injury') &&
    isString(item.summary) &&
    (item.conversation_prompt === null || isString(item.conversation_prompt))
  );
}

function isGuardianArchive(value: unknown): value is GuardianArchive {
  if (typeof value !== 'object' || value === null) return false;
  const archive = value as Record<string, unknown>;
  return (
    isString(archive.child_display_name) &&
    isString(archive.expires_at) &&
    Array.isArray(archive.notifications) &&
    archive.notifications.every(isNotification)
  );
}

export function createGuardianArchiveClient(
  token: string,
  fetchImplementation?: typeof fetch
): ApiClient {
  return new ApiClient({
    accessToken: () => token,
    fetch: fetchImplementation
  });
}

/**
 * 現行画面と同じく、HTTPエラー時だけ保存済みトークンを破棄する。
 * 一時的な通信障害ではURLを再発行してもらわずに再試行できるよう保持する。
 */
export async function loadGuardianArchive(
  client: ApiClient,
  sessionStorage: GuardianStorage,
  signal?: AbortSignal
): Promise<GuardianArchiveLoadResult> {
  try {
    const archive = await client.requestJson<unknown>('/guardian/archive', {
      signal
    });
    if (!isGuardianArchive(archive)) throw new ApiInvalidResponseError();
    return { status: 'success', archive };
  } catch (error) {
    if (error instanceof ApiRequestCancelledError) {
      return { status: 'cancelled' };
    }
    if (error instanceof ApiHttpError) {
      sessionStorage.removeItem(GUARDIAN_ARCHIVE_TOKEN_STORAGE_KEY);
      return { status: 'invalid-link' };
    }
    return { status: 'network-error' };
  }
}
