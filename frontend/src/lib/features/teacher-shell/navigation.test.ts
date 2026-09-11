import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/svelte';

import NavigationFixture from './NavigationFixture.svelte';
import {
  canAccessTeacherRoute,
  isAdminRoute,
  teacherNavItems,
  teacherPageTitle
} from './navigation';

describe('teacher shell navigation', () => {
  it('管理者専用routeだけを識別する', () => {
    expect(isAdminRoute('/teacher-next/settings/')).toBe(true);
    expect(isAdminRoute('/teacher-next/audit/')).toBe(true);
    expect(isAdminRoute('/teacher-next/review/record-id/')).toBe(false);
  });

  it('一般の先生による管理者用URLの直接表示を拒否する', () => {
    expect(canAccessTeacherRoute('/teacher-next/settings/', false)).toBe(false);
    expect(
      canAccessTeacherRoute('/teacher-next/review/record-id/', false)
    ).toBe(true);
  });

  it('レビュー詳細と手入力に固有の見出しを付ける', () => {
    expect(teacherPageTitle('/teacher-next/review/abc/')).toBe(
      '日誌のレビュー'
    );
    expect(teacherPageTitle('/teacher-next/review/new/')).toBe('日誌の手入力');
  });

  it('一般の先生向け一覧に管理者用URLを含めない', () => {
    expect(teacherNavItems(false).map((item) => item.href)).not.toContain(
      '/teacher-next/settings/'
    );
  });

  it('一般の先生のDOMから管理者ナビを除去し、現在地を示す', () => {
    render(NavigationFixture, {
      isSchoolAdmin: false,
      currentPath: '/teacher-next/notifications/'
    });

    expect(screen.queryByRole('link', { name: '園の設定' })).toBeNull();
    expect(screen.getByRole('link', { name: '通知状況' })).toHaveAttribute(
      'aria-current',
      'page'
    );
  });
});
