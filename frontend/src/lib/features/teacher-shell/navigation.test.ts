import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/svelte';

import NavigationFixture from './NavigationFixture.svelte';
import {
  canAccessTeacherRoute,
  isAdminRoute,
  teacherNavItems,
  teacherPageTitle
} from './navigation';
import type { NavigationBadgeCounts } from './navigation-badges';

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

  it('ナビ該当項目へ通常・注意バッジを渡す', () => {
    const counts: NavigationBadgeCounts = {
      pending_review_records: 3,
      notification_attention: 4,
      failed_audio_jobs: 2,
      invitations_not_issued: 1,
      readiness_issues: 5
    };
    const items = teacherNavItems(true, counts);
    const byHref = new Map(items.map((item) => [item.href, item]));

    expect(byHref.get('/teacher/review/')?.badge).toBe('3件');
    expect(byHref.get('/teacher/review/')?.badgeTone).toBe('default');
    expect(byHref.get('/teacher/review/')?.badgeAriaLabel).toBe(
      'レビュー待ち3件'
    );
    expect(byHref.get('/teacher/notifications/')?.badge).toBe('!4件');
    expect(byHref.get('/teacher/notifications/')?.badgeTone).toBe('warning');
    expect(byHref.get('/teacher/audio-jobs/')?.badge).toBe('!2件');
    expect(byHref.get('/teacher/children/')?.badge).toBe('1件');
    expect(byHref.get('/teacher/readiness/')?.badge).toBe('!5項目');
  });

  it('ゼロは非表示、100以上は99+表示でaria-labelに正確な件数を残す', () => {
    const counts: NavigationBadgeCounts = {
      pending_review_records: 0,
      notification_attention: 100,
      failed_audio_jobs: 123,
      invitations_not_issued: 0,
      readiness_issues: 100
    };
    const byHref = new Map(
      teacherNavItems(true, counts).map((item) => [item.href, item])
    );

    expect(byHref.get('/teacher/review/')?.badge).toBeUndefined();
    expect(byHref.get('/teacher/children/')?.badge).toBeUndefined();
    expect(byHref.get('/teacher/notifications/')?.badge).toBe('!99+');
    expect(byHref.get('/teacher/notifications/')).toMatchObject({
      badgeAriaLabel: '通知状況の要確認100件'
    });
    expect(byHref.get('/teacher/audio-jobs/')).toMatchObject({
      badge: '!99+',
      badgeAriaLabel: '音声処理の失敗123件'
    });
    expect(byHref.get('/teacher/readiness/')).toMatchObject({
      badge: '!99+',
      badgeAriaLabel: '稼働準備で確認が必要な項目100項目'
    });
  });

  it('休止中は従来の12項目に用途を説明するガイドを持つ', () => {
    const items = teacherNavItems(true);
    expect(items).toHaveLength(12);
    for (const item of items) {
      expect(item.guide).toBeTruthy();
    }
  });

  it('休止中は配信ナビと直接URLを閉じ、再開時に戻す', () => {
    expect(
      teacherNavItems(true).some(
        (item) => item.href === '/teacher/daily-delivery/'
      )
    ).toBe(false);
    expect(canAccessTeacherRoute('/teacher/daily-delivery/', true)).toBe(false);
    expect(canAccessTeacherRoute('/teacher/daily-delivery/', false, true)).toBe(
      true
    );
    expect(
      teacherNavItems(false, undefined, true).some(
        (item) => item.href === '/teacher/daily-delivery/'
      )
    ).toBe(true);
  });

  it.each([false, true])('配信ナビのDOMは全体設定 %s に従う', (enabled) => {
    render(NavigationFixture, { classDeliveryEnabled: enabled });
    expect(screen.queryByRole('link', { name: '今日の配信' }) !== null).toBe(
      enabled
    );
  });

  it('バッジ合成後もガイドを保持する', () => {
    const counts: NavigationBadgeCounts = {
      pending_review_records: 3,
      notification_attention: 4,
      failed_audio_jobs: 2,
      invitations_not_issued: 1,
      readiness_issues: 5
    };
    const byHref = new Map(
      teacherNavItems(true, counts).map((item) => [item.href, item])
    );

    expect(byHref.get('/teacher/review/')).toMatchObject({
      badge: '3件',
      guide: 'AI候補や手入力の日誌を確認し、承認・却下します。'
    });
    expect(byHref.get('/teacher/readiness/')).toMatchObject({
      badge: '!5項目',
      guide: '本番運用に必要な設定や外部連携の不足を確認します。'
    });
  });

  it('一般の先生には管理者用バッジを渡さない', () => {
    const counts: NavigationBadgeCounts = {
      pending_review_records: 1,
      notification_attention: 1,
      failed_audio_jobs: 1,
      invitations_not_issued: 9,
      readiness_issues: 9
    };
    const byHref = new Map(
      teacherNavItems(false, counts).map((item) => [item.href, item])
    );

    expect(byHref.get('/teacher/children/')?.badge).toBeUndefined();
    expect(byHref.get('/teacher/children/')?.badgeTone).toBeUndefined();
    expect(byHref.has('/teacher/readiness/')).toBe(false);
  });
});
