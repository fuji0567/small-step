import { cleanup, render, screen, waitFor } from '@testing-library/svelte';
import { afterEach, describe, expect, it } from 'vitest';

import NotFoundView from './NotFoundView.svelte';

afterEach(cleanup);

describe('NotFoundView', () => {
  it('日本語404と実URLを表示し見出しへフォーカスする', async () => {
    render(NotFoundView);

    const heading = screen.getByRole('heading', {
      name: 'ページが見つかりません'
    });
    expect(screen.getByText('404')).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: '先生用ホームへ戻る' })
    ).toHaveAttribute('href', '/teacher/');
    await waitFor(() => expect(heading).toHaveFocus());
  });
});
