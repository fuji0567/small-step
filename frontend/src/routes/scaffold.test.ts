import { cleanup, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it } from 'vitest';

import TeacherPageFixture from '$lib/features/dashboard/DashboardPageFixture.test.svelte';
import GuardianPage from './guardian-next/+page.svelte';

afterEach(cleanup);

describe('preview routes', () => {
  it('renders the teacher preview shell', () => {
    render(TeacherPageFixture);
    expect(
      screen.getByRole('heading', { name: '今日の状況' })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: /レビュー待ち 0件/ })
    ).toHaveAttribute('href', '/teacher-next/review/');
  });

  it('renders the guardian preview shell', () => {
    render(GuardianPage);
    expect(
      screen.getByRole('heading', { name: '配信アーカイブ' })
    ).toBeInTheDocument();
  });
});
