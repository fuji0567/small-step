import AxeBuilder from '@axe-core/playwright';
import { expect, mockApi, test } from './fixtures';

const config = {
  auth_mode: 'supabase',
  supabase_url: 'https://invitation-fixture.supabase.co',
  supabase_publishable_key: 'public-fixture-key',
  teacher_invitations_enabled: true
};

const teacher = {
  id: 'invited-teacher',
  school_id: 'school-1',
  name: '招待先生',
  email: 'teacher@example.com',
  role: 'teacher',
  is_active: true,
  auth_user_id: null,
  invitation_sent_at: null as string | null,
  disabled_at: null,
  created_at: '2026-09-18T00:00:00Z'
};

test('園管理者が先生登録と招待をまとめて行える', async ({ page }) => {
  await mockApi(page);
  let registered = false;
  let sentAt: string | null = null;
  await page.addInitScript(() => {
    sessionStorage.setItem('small-step.access-token', 'admin-fixture-token');
  });
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/auth/config') {
      await route.fulfill({ json: config });
    } else if (path === '/api/v1/auth/me') {
      await route.fulfill({
        json: { ...teacher, id: 'admin', role: 'school_admin' }
      });
    } else if (path === '/api/v1/teachers') {
      if (route.request().method() === 'POST') {
        expect(route.request().postDataJSON()).toMatchObject({
          name: teacher.name,
          email: teacher.email,
          role: 'teacher'
        });
        registered = true;
        await route.fulfill({ json: teacher, status: 201 });
      } else {
        await route.fulfill({
          json: registered ? [{ ...teacher, invitation_sent_at: sentAt }] : []
        });
      }
    } else if (path === '/api/v1/teachers/invited-teacher/invite') {
      expect(registered).toBe(true);
      expect(route.request().method()).toBe('POST');
      expect(route.request().postData()).toBeNull();
      sentAt = '2026-09-18T01:00:00Z';
      await route.fulfill({
        json: { ...teacher, invitation_sent_at: sentAt }
      });
    } else {
      await route.fallback();
    }
  });
  await page.goto('/teacher/teachers/');
  await page.getByLabel('先生名', { exact: true }).fill(teacher.name);
  await page.getByLabel('メールアドレス', { exact: true }).fill(teacher.email);
  await page.getByRole('button', { name: '登録して招待を送る' }).click();
  await expect(page.getByText('招待送信済み（ログイン待ち）')).toBeVisible();
  await expect(
    page.getByText(
      '先生を登録し、招待メールの送信を受け付けました。メールからパスワードを設定してください。'
    )
  ).toBeVisible();
});

test('招待メールからパスワードを設定し、一般の先生としてログインする', async ({
  page
}) => {
  await mockApi(page);
  let passwordRequests = 0;
  await page.route('**/api/v1/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    if (path === '/api/v1/auth/config') {
      await route.fulfill({ json: config });
    } else if (path === '/api/v1/auth/me') {
      await route.fulfill({ status: 403, json: { detail: 'not linked' } });
    } else if (path === '/api/v1/auth/link-teacher') {
      await route.fulfill({ json: teacher });
    } else {
      await route.fallback();
    }
  });
  await page.route(
    'https://invitation-fixture.supabase.co/auth/v1/user',
    async (route) => {
      passwordRequests++;
      expect(route.request().method()).toBe('PUT');
      expect(route.request().headers()['apikey']).toBe('public-fixture-key');
      expect(route.request().headers()['authorization']).toBe(
        'Bearer invite-fixture-token'
      );
      expect(route.request().postDataJSON()).toEqual({
        password: 'fixture-password'
      });
      await route.fulfill({ json: {} });
    }
  );
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(
    '/teacher/#type=invite&access_token=invite-fixture-token&refresh_token=unused'
  );
  await expect(
    page.getByRole('heading', { name: '招待された先生のパスワード設定' })
  ).toBeVisible();
  expect(new URL(page.url()).hash).toBe('');
  expect(
    await page.evaluate(() => sessionStorage.getItem('small-step.access-token'))
  ).toBeNull();
  await page.getByLabel('パスワード', { exact: true }).fill('fixture-password');
  await page
    .getByLabel('パスワード（確認）', { exact: true })
    .fill('different');
  await page
    .getByRole('button', { name: 'パスワードを設定して始める' })
    .click();
  await expect(
    page.getByText('確認用のパスワードが一致しません。')
  ).toBeVisible();
  expect(passwordRequests).toBe(0);
  const scan = await new AxeBuilder({ page }).analyze();
  expect(
    scan.violations.filter((issue) =>
      ['serious', 'critical'].includes(issue.impact ?? '')
    )
  ).toEqual([]);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth
    )
  ).toBe(true);
  await page
    .getByLabel('パスワード（確認）', { exact: true })
    .fill('fixture-password');
  await page
    .getByRole('button', { name: 'パスワードを設定して始める' })
    .click();
  await expect(
    page
      .getByRole('navigation', { name: '先生用メニュー' })
      .getByRole('link', { name: /^レビュー待ち/ })
  ).toBeVisible();
  await expect(page.getByRole('link', { name: '先生管理' })).toHaveCount(0);
  expect(passwordRequests).toBe(1);
  expect(
    await page.evaluate(() => sessionStorage.getItem('small-step.access-token'))
  ).toBe('invite-fixture-token');
});
