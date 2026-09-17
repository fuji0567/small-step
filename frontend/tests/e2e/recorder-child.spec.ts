import { expect, mockApi, test } from './fixtures';

test('録音の園児候補は先生の確認まで承認できない', async ({ page }) => {
  await mockApi(page, { recorderChild: true });
  await page.goto('/teacher/review/record-1/');

  await expect(page.getByLabel('園児', { exact: true })).toHaveValue('child-1');
  await expect(page.getByText(/録音からの園児候補: ひなた/)).toBeVisible();
  const approve = page.getByRole('button', { name: '承認する', exact: true });
  const confirmed = page.getByRole('checkbox', {
    name: '選択した園児がこの出来事の対象であることを確認しました'
  });
  await expect(confirmed).not.toBeChecked();
  await expect(approve).toBeDisabled();
  await confirmed.check();
  await expect(approve).toBeEnabled();
  await page.getByLabel('園児', { exact: true }).selectOption('');
  await expect(confirmed).not.toBeChecked();
  await expect(approve).toBeDisabled();
});
