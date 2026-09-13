import { expect, guardianArchiveUrl, mockApi, test } from './fixtures';

test('有効なURLはフラグメントを消して表示し、再読み込みできる', async ({
  page
}) => {
  await mockApi(page);
  await page.goto(guardianArchiveUrl());

  await expect(page).toHaveURL(/\/guardian\/$/);
  await expect(
    page.getByRole('heading', { name: 'ひなたさんのお知らせ' })
  ).toBeVisible();
  await expect(
    page.getByText('お友だちに自分から声をかけて遊べました。')
  ).toBeVisible();

  await page.reload();
  await expect(
    page.getByRole('heading', { name: 'ひなたさんのお知らせ' })
  ).toBeVisible();
  expect(new URL(page.url()).hash).toBe('');
});

test('無効なURLは秘密をアドレスバーと保存領域から除去する', async ({
  page
}) => {
  await mockApi(page, { guardian: 'invalid' });
  await page.goto(guardianArchiveUrl());

  await expect(page).toHaveURL(/\/guardian\/$/);
  await expect(
    page.getByRole('alert').getByText('このアーカイブは開けません')
  ).toBeVisible();
  expect(new URL(page.url()).hash).toBe('');

  await page.reload();
  await expect(
    page.getByText(
      'URLが見つかりません。園から届いた最新のURLを開いてください。'
    )
  ).toBeVisible();
});
