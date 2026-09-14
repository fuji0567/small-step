import { expect, mockApi, test } from './fixtures';

test('デスクトップ左ナビに各通知バッジを表示し、完全なaria-labelを持つ', async ({
  page
}) => {
  await page.setViewportSize({ width: 1280, height: 720 });
  await mockApi(page);
  await page.goto('/teacher/');

  await expect(page.getByRole('heading', { name: '今日の状況' })).toBeVisible();

  const navigation = page.getByRole('navigation', {
    name: '先生用メニュー'
  });
  const main = page.locator('.ss-app-shell__main');
  await expect(navigation).toBeVisible();
  expect((await navigation.boundingBox())?.x).toBeLessThan(
    (await main.boundingBox())?.x ?? Number.POSITIVE_INFINITY
  );

  const badges = [
    {
      linkName: 'レビュー待ち レビュー待ち3件',
      visibleLabel: '3件',
      ariaLabel: 'レビュー待ち3件'
    },
    {
      linkName: '通知状況 通知状況の要確認4件',
      visibleLabel: '!4件',
      ariaLabel: '通知状況の要確認4件'
    },
    {
      linkName: '音声処理状況 音声処理の失敗5件',
      visibleLabel: '!5件',
      ariaLabel: '音声処理の失敗5件'
    },
    {
      linkName: '園児・保護者 招待コード未発行6件',
      visibleLabel: '6件',
      ariaLabel: '招待コード未発行6件'
    },
    {
      linkName: '稼働準備チェック 稼働準備で確認が必要な項目7項目',
      visibleLabel: '!7項目',
      ariaLabel: '稼働準備で確認が必要な項目7項目'
    }
  ];

  for (const { linkName, visibleLabel, ariaLabel } of badges) {
    const link = navigation.getByRole('link', { name: linkName });
    await expect(link).toBeVisible();
    const badge = link.locator('[aria-label]');
    await expect(badge).toHaveText(visibleLabel);
    await expect(badge).toHaveAttribute('aria-label', ariaLabel);
  }
});
