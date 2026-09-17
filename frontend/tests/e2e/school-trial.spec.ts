import { expect, mockApi, test } from './fixtures';

test('試用中の表示と、本番配信を有効にする二段階確認', async ({ page }) => {
  await mockApi(page, { trialSchool: true });
  await page.goto('/teacher/settings/');
  await expect(
    page.getByRole('button', { name: '本番モードへ切り替え' })
  ).toBeDisabled();
  await expect(
    page.getByText('試用中（保護者への配信なし）').first()
  ).toBeVisible();
  await page.getByRole('checkbox').check();
  await page.getByRole('button', { name: '本番モードへ切り替え' }).click();
  await page.getByRole('button', { name: 'キャンセル' }).click();
  await expect(
    page.getByRole('button', { name: '本番モードへ切り替え' })
  ).toBeVisible();
  await page.getByRole('button', { name: '本番モードへ切り替え' }).click();
  await page.getByRole('button', { name: '配信を有効にする' }).click();
  await expect(
    page.getByRole('button', { name: '試用モードへ切り替え' })
  ).toBeVisible();
  await expect(page.getByText('試用中（保護者への配信なし）')).toHaveCount(0);
});
