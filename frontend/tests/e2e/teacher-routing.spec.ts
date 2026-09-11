import { expect, mockApi, test } from './fixtures';

test.beforeEach(async ({ page }) => {
  await mockApi(page);
});

test('ホームからレビュー待ちへURLで遷移する', async ({ page }) => {
  await page.goto('/teacher/');
  await expect(page.getByRole('heading', { name: '今日の状況' })).toBeVisible();

  await page
    .getByRole('navigation', { name: '先生用メニュー' })
    .getByRole('link', { name: 'レビュー待ち' })
    .click();

  await expect(page).toHaveURL(/\/teacher\/review\/$/);
  await expect(
    page.getByRole('heading', { name: 'レビュー待ち日誌' })
  ).toBeVisible();
});

test('日誌の深いURLは再読み込みと戻る・進むに耐える', async ({ page }) => {
  await page.goto('/teacher/review/record-1/');
  await expect(
    page.getByRole('heading', { name: '日誌のレビュー', level: 2 })
  ).toBeVisible();
  await expect(page.getByLabel('保護者へ伝える内容')).toHaveValue(
    'お友だちに自分から声をかけて遊べました。'
  );

  await page.reload();
  await expect(page).toHaveURL(/\/teacher\/review\/record-1\/$/);
  await expect(page.getByLabel('保護者へ伝える内容')).toHaveValue(
    'お友だちに自分から声をかけて遊べました。'
  );

  await page.getByRole('link', { name: 'レビュー待ち一覧へ戻る' }).click();
  await expect(page).toHaveURL(/\/teacher\/review\/$/);

  await page.goBack();
  await expect(page).toHaveURL(/\/teacher\/review\/record-1\/$/);
  await expect(
    page.getByRole('heading', { name: '日誌のレビュー', level: 2 })
  ).toBeVisible();

  await page.goForward();
  await expect(page).toHaveURL(/\/teacher\/review\/$/);
  await expect(
    page.getByRole('heading', { name: 'レビュー待ち日誌' })
  ).toBeVisible();
});

test('未定義の先生用URLはクライアント404を表示する', async ({ page }) => {
  await page.goto('/teacher/not-a-page/');

  await expect(page).toHaveURL(/\/teacher\/not-a-page\/$/);
  await expect(
    page.getByRole('heading', { name: 'ページが見つかりません' })
  ).toBeVisible();
  await expect(page.getByText('404', { exact: true })).toBeVisible();
});
