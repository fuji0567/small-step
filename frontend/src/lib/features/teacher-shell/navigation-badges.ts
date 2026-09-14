import type { ApiClient } from '$lib/api';

export const NAVIGATION_BADGE_FIELDS = [
  'pending_review_records',
  'notification_attention',
  'failed_audio_jobs',
  'invitations_not_issued',
  'readiness_issues'
] as const;

export type NavigationBadgeField = (typeof NAVIGATION_BADGE_FIELDS)[number];

export type NavigationBadgeCounts = {
  [Field in NavigationBadgeField]: number;
};

export const EMPTY_NAVIGATION_BADGES: NavigationBadgeCounts = {
  pending_review_records: 0,
  notification_attention: 0,
  failed_audio_jobs: 0,
  invitations_not_issued: 0,
  readiness_issues: 0
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/**
 * Validate the count-only response instead of allowing malformed values to
 * reach the navigation. This keeps null, negative, fractional, and unsafe
 * integer values from being rendered as misleading status indicators.
 */
export function parseNavigationBadgeCounts(
  value: unknown
): NavigationBadgeCounts {
  if (!isRecord(value)) {
    throw new Error('ナビゲーションバッジの応答が不正です。');
  }

  const counts = {} as NavigationBadgeCounts;
  for (const field of NAVIGATION_BADGE_FIELDS) {
    const count = value[field];
    if (
      typeof count !== 'number' ||
      !Number.isSafeInteger(count) ||
      count < 0
    ) {
      throw new Error('ナビゲーションバッジの応答が不正です。');
    }
    counts[field] = count;
  }
  return counts;
}

export class NavigationBadgeService {
  readonly #api: ApiClient;

  constructor(api: ApiClient) {
    this.#api = api;
  }

  async load(
    schoolId: string,
    signal?: AbortSignal
  ): Promise<NavigationBadgeCounts> {
    const params = new URLSearchParams({ school_id: schoolId });
    const value = await this.#api.requestJson<unknown>(
      `navigation-badges?${params.toString()}`,
      { signal }
    );
    if (value === null) {
      throw new Error('ナビゲーションバッジの応答が不正です。');
    }
    return parseNavigationBadgeCounts(value);
  }
}
