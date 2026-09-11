import { render, screen } from '@testing-library/svelte';
import { describe, expect, it } from 'vitest';

import GuardianPage from './guardian-next/+page.svelte';
import TeacherPage from './teacher-next/+page.svelte';

describe('preview routes', () => {
  it('renders the teacher preview shell', () => {
    render(TeacherPage);
    expect(
      screen.getByRole('heading', { name: '先生用画面' })
    ).toBeInTheDocument();
  });

  it('renders the guardian preview shell', () => {
    render(GuardianPage);
    expect(
      screen.getByRole('heading', { name: '配信アーカイブ' })
    ).toBeInTheDocument();
  });
});
