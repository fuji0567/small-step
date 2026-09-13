import { expect, test as base, type Page, type Route } from '@playwright/test';

const GUARDIAN_TEST_TOKEN = 'ssa_playwright-fixture';

const school = {
  id: 'school-1',
  name: 'ひだまり園',
  timezone: 'Asia/Tokyo',
  digest_time: '17:00:00',
  created_at: '2026-01-01T00:00:00Z'
};

const child = {
  id: 'child-1',
  school_id: school.id,
  display_name: 'ひなた',
  guardian_line_user_id: null,
  is_active: true,
  archived_at: null,
  created_at: '2026-01-01T00:00:00Z'
};

const record = {
  id: 'record-1',
  school_id: school.id,
  teacher_id: 'teacher-1',
  child_id: child.id,
  category: 'growth',
  status: 'pending_review',
  source_event_id: 'event-1',
  confidence: 0.92,
  occurred_at: '2026-09-12T00:00:00Z',
  summary: 'お友だちに自分から声をかけて遊べました。',
  conversation_prompt: '今日は誰と遊んだの？',
  anonymized_context: null,
  reviewed_at: null,
  created_at: '2026-09-12T00:00:00Z',
  updated_at: '2026-09-12T00:00:00Z'
};

type GuardianResponse = 'valid' | 'invalid';

function json(route: Route, value: unknown, status = 200): Promise<void> {
  return route.fulfill({
    status,
    contentType: 'application/json; charset=utf-8',
    body: JSON.stringify(value)
  });
}

export async function mockApi(
  page: Page,
  options: { guardian?: GuardianResponse } = {}
): Promise<void> {
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());

    switch (url.pathname) {
      case '/api/v1/auth/config':
        await json(route, {
          auth_mode: 'development',
          supabase_url: null,
          supabase_publishable_key: null
        });
        return;
      case '/api/v1/schools':
        await json(route, [school]);
        return;
      case '/api/v1/records':
        await json(route, [record]);
        return;
      case '/api/v1/records/record-1':
        await json(route, record);
        return;
      case '/api/v1/children':
        await json(route, [child]);
        return;
      case '/api/v1/notifications':
      case '/api/v1/audio-jobs':
      case '/api/v1/line/link-invitations/active':
        await json(route, []);
        return;
      case '/api/v1/guardian/archive': {
        const authorized =
          request.headers()['authorization'] ===
          `Bearer ${GUARDIAN_TEST_TOKEN}`;
        if (options.guardian === 'invalid' || !authorized) {
          await json(route, { detail: 'invalid link' }, 401);
          return;
        }
        await json(route, {
          child_display_name: child.display_name,
          expires_at: '2030-09-12T09:00:00Z',
          notifications: [
            {
              delivered_at: '2026-09-12T08:00:00Z',
              category: 'growth',
              summary: record.summary,
              conversation_prompt: record.conversation_prompt
            }
          ]
        });
        return;
      }
      default:
        await json(route, { detail: 'not mocked' }, 404);
    }
  });
}

export function guardianArchiveUrl(): string {
  return `/guardian/#${GUARDIAN_TEST_TOKEN}`;
}

export const test = base;
export { expect };
