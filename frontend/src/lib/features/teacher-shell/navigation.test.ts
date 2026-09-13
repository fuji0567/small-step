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
    expect(isAdminRoute('/teacher/settings/')).toBe(true);
    expect(isAdminRoute('/teacher/audit/')).toBe(true);
    expect(isAdminRoute('/teacher/review/record-id/')).toBe(false);
  });

  it('一般の先生による管理者用URLの直接表示を拒否する', () => {
    expect(canAccessTeacherRoute('/teacher/settings/', false)).toBe(false);
    expect(canAccessTeacherRoute('/teacher/review/record-id/', false)).toBe(
      true
    );
  });

  it('レビュー詳細と手入力に固有の見出しを付ける', () => {
    expect(teacherPageTitle('/teacher/review/abc/')).toBe('日誌のレビュー');
    expect(teacherPageTitle('/teacher/review/new/')).toBe('日誌の手入力');
  });

  it('一般の先生向け一覧に管理者用URLを含めない', () => {
    const hrefs = teacherNavItems(false).map((item) => item.href);
    expect(hrefs).toContain('/teacher/records/');
    expect(hrefs).not.toContain('/teacher/settings/');
  });

  it('一般の先生のDOMから管理者ナビを除去し、現在地を示す', () => {
    render(NavigationFixture, {
      isSchoolAdmin: false,
      currentPath: '/teacher/notifications/'
    });

    expect(screen.queryByRole('link', { name: '園の設定' })).toBeNull();
    expect(screen.getByRole('link', { name: '通知状況' })).toHaveAttribute(
      'aria-current',
      'page'
    );
  });
});
