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

test('ボタンの補足ガイドをフォーカスとホバーで確認しEscで閉じられる', async ({
  page
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/teacher/review/record-1/');

  const approveButton = page.getByRole('button', { name: '承認する' });
  const guide = page.getByRole('tooltip', {
    name: '編集内容を保存し、保護者へのLINE通知を準備します。'
  });

  await expect(guide).toBeHidden();
  await approveButton.focus();
  await expect(guide).toBeVisible();
  expect(
    await guide.evaluate((element) => getComputedStyle(element).backgroundColor)
  ).toMatch(/0\.88|88%/);
  expect(
    Number(await guide.evaluate((element) => getComputedStyle(element).zIndex))
  ).toBeGreaterThan(10);
  const guideBox = await guide.boundingBox();
  expect(guideBox).not.toBeNull();
  expect(guideBox!.x).toBeGreaterThanOrEqual(0);
  expect(guideBox!.x + guideBox!.width).toBeLessThanOrEqual(390);
  const guideId = await guide.getAttribute('id');
  expect(guideId).not.toBeNull();
  await expect(approveButton).toHaveAttribute('aria-describedby', guideId!);

  await guide.hover();
  await expect(guide).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(guide).toBeHidden();

  await approveButton.evaluate((button) => button.blur());
  await page.mouse.move(0, 0);
  await approveButton.hover();
  await page.waitForTimeout(300);
  await expect(guide).toBeHidden();
  await expect(guide).toBeVisible();
});

test('左ナビの補足ガイドをフォーカスとホバーで確認しEscで閉じられる', async ({
  page
}) => {
  await page.goto('/teacher/');
  await expect(page.getByRole('heading', { name: '今日の状況' })).toBeVisible();

  const reviewLink = page.getByRole('link', {
    name: 'レビュー待ち レビュー待ち3件'
  });
  const navigation = page.getByRole('navigation', {
    name: '先生用メニュー'
  });
  const guide = page.getByRole('tooltip', {
    name: 'AI候補や手入力の日誌を確認し、承認・却下します。'
  });

  await expect(guide).toBeHidden();
  await reviewLink.focus();
  await expect(guide).toBeVisible();
  await expect(guide.getByText('レビュー待ち3件')).toBeVisible();
  expect(
    await guide.evaluate((element) => getComputedStyle(element).backgroundColor)
  ).toMatch(/0\.88|88%/);
  expect(
    Number(await guide.evaluate((element) => getComputedStyle(element).zIndex))
  ).toBeGreaterThan(10);
  expect(
    Number(
      await navigation.evaluate((element) => getComputedStyle(element).zIndex)
    )
  ).toBeGreaterThan(10);
  const guideId = await guide.getAttribute('id');
  expect(guideId).not.toBeNull();
  await expect(reviewLink).toHaveAttribute('aria-describedby', guideId!);

  await guide.hover();
  await expect(guide).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(guide).toBeHidden();

  await reviewLink.evaluate((link) => link.blur());
  await page.mouse.move(0, 0);
  await reviewLink.hover();
  await page.waitForTimeout(300);
  await expect(guide).toBeHidden();
  await expect(guide).toBeVisible();
});

test('モバイル横ナビでもガイドが画面内に収まる', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/teacher/');
  await expect(page.getByRole('heading', { name: '今日の状況' })).toBeVisible();

  const reviewLink = page.getByRole('link', {
    name: 'レビュー待ち レビュー待ち3件'
  });
  const guide = page.getByRole('tooltip', {
    name: 'AI候補や手入力の日誌を確認し、承認・却下します。'
  });

  await reviewLink.focus();
  await expect(guide).toBeVisible();
  const guideBox = await guide.boundingBox();
  expect(guideBox).not.toBeNull();
  expect(guideBox!.x).toBeGreaterThanOrEqual(0);
  expect(guideBox!.x + guideBox!.width).toBeLessThanOrEqual(390);
  expect(guideBox!.y).toBeGreaterThanOrEqual(0);
  expect(guideBox!.y + guideBox!.height).toBeLessThanOrEqual(844);
});
