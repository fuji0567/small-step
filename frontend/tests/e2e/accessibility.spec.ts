import AxeBuilder from '@axe-core/playwright';

import { expect, mockApi, test } from './fixtures';

test.beforeEach(async ({ page }) => {
  await mockApi(page);
});

test('キーボードで本文へ移動でき、重大なaxe違反がない', async ({ page }) => {
  await page.goto('/teacher/');
  await expect(page.getByRole('heading', { name: '今日の状況' })).toBeVisible();

  await page.evaluate(() =>
    (document.activeElement as HTMLElement | null)?.blur()
  );
  await page.keyboard.press('Tab');
  const skipLink = page.getByRole('link', { name: '本文へ移動' });
  await expect(skipLink).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(page.locator('#main-content')).toBeFocused();

  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze();
  const blocking = results.violations.filter((violation) =>
    ['serious', 'critical'].includes(violation.impact ?? '')
  );
  expect(blocking).toEqual([]);
});

test('モバイル幅でも主要内容が画面外へはみ出さない', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/teacher/');
  await expect(page.getByRole('heading', { name: '今日の状況' })).toBeVisible();

  const dimensions = await page.evaluate(() => ({
    clientWidth: document.documentElement.clientWidth,
    scrollWidth: document.documentElement.scrollWidth
  }));
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.clientWidth);

  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze();
  const blocking = results.violations.filter((violation) =>
    ['serious', 'critical'].includes(violation.impact ?? '')
  );
  expect(blocking).toEqual([]);
});
