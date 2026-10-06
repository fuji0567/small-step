import type { AppShellNavItem } from '$lib/components';

import {
  EMPTY_NAVIGATION_BADGES,
  type NavigationBadgeCounts
} from './navigation-badges';

export const TEACHER_NAV_ITEMS = [
  {
    href: '/teacher/',
    label: 'ホーム',
    icon: 'home',
    guide: '今日の要確認件数と園全体の状況を確認します。'
  },
  {
    href: '/teacher/review/',
    label: 'レビュー待ち',
    icon: 'review',
    guide: 'AI候補や手入力の日誌を確認し、承認・却下します。'
  },
  {
    href: '/teacher/records/',
    label: '記録履歴',
    icon: 'history',
    guide: '過去の日誌を検索し、内容や配信状態を確認します。'
  },
  {
    href: '/teacher/notifications/',
    label: '通知状況',
    icon: 'notifications',
    guide: 'LINE通知の送信予定・結果・失敗を確認します。'
  },
  {
    href: '/teacher/daily-delivery/',
    label: '今日の配信',
    icon: 'notifications',
    guide: 'クラスのお便りと、先生が確認する個人成長の配信対象を管理します。'
  },
  {
    href: '/teacher/audio-jobs/',
    label: '音声処理状況',
    icon: 'audio',
    guide: '音声処理の進み具合や失敗内容を確認します。'
  },
  {
    href: '/teacher/children/',
    label: '園児・保護者',
    icon: 'child',
    guide: '園児情報、保護者のLINE連携、招待コードを管理します。'
  },
  {
    href: '/teacher/voice-consent/',
    label: '声紋設定',
    icon: 'microphone',
    guide: '先生の声紋登録に関する同意状況を確認・変更します。'
  }
] as const satisfies readonly AppShellNavItem[];

export const ADMIN_NAV_ITEMS = [
  {
    href: '/teacher/settings/',
    label: '園の設定',
    icon: 'schedule',
    guide: '成長記録をまとめて配信する既定時刻を設定します。'
  },
  {
    href: '/teacher/teachers/',
    label: '先生管理',
    icon: 'group',
    guide: '先生の登録、権限変更、利用停止を管理します。'
  },
  {
    href: '/teacher/devices/',
    label: '録音端末',
    icon: 'microphone',
    guide: '録音端末の登録、担当先生、接続用キーを管理します。'
  },
  {
    href: '/teacher/readiness/',
    label: '稼働準備チェック',
    icon: 'checklist',
    guide: '本番運用に必要な設定や外部連携の不足を確認します。'
  },
  {
    href: '/teacher/audit/',
    label: '操作履歴',
    icon: 'privacy',
    guide: '先生や管理者が行った操作の履歴を確認します。'
  }
] as const satisfies readonly AppShellNavItem[];

function countBadge(
  count: number,
  suffix: '件' | '項目',
  ariaLabel: string,
  warning = false
): Pick<AppShellNavItem, 'badge' | 'badgeAriaLabel' | 'badgeTone'> | null {
  if (count === 0) return null;
  const visualCount = count >= 100 ? '99+' : `${count}${suffix}`;
  return {
    badge: `${warning ? '!' : ''}${visualCount}`,
    badgeAriaLabel: ariaLabel,
    badgeTone: warning ? 'warning' : 'default'
  };
}

function badgeFor(
  href: string,
  counts: NavigationBadgeCounts,
  isSchoolAdmin: boolean
): Pick<AppShellNavItem, 'badge' | 'badgeAriaLabel' | 'badgeTone'> | null {
  switch (href) {
    case '/teacher/review/':
      return countBadge(
        counts.pending_review_records,
        '件',
        `レビュー待ち${counts.pending_review_records}件`
      );
    case '/teacher/notifications/':
      return countBadge(
        counts.notification_attention,
        '件',
        `通知状況の要確認${counts.notification_attention}件`,
        true
      );
    case '/teacher/audio-jobs/':
      return countBadge(
        counts.failed_audio_jobs,
        '件',
        `音声処理の失敗${counts.failed_audio_jobs}件`,
        true
      );
    case '/teacher/children/':
      return isSchoolAdmin
        ? countBadge(
            counts.invitations_not_issued,
            '件',
            `招待コード未発行${counts.invitations_not_issued}件`
          )
        : null;
    case '/teacher/readiness/':
      return isSchoolAdmin
        ? countBadge(
            counts.readiness_issues,
            '項目',
            `稼働準備で確認が必要な項目${counts.readiness_issues}項目`,
            true
          )
        : null;
    default:
      return null;
  }
}

export function teacherNavItems(
  isSchoolAdmin: boolean,
  counts: NavigationBadgeCounts = EMPTY_NAVIGATION_BADGES,
  classDeliveryEnabled = false
): AppShellNavItem[] {
  const items = [
    ...TEACHER_NAV_ITEMS,
    ...(isSchoolAdmin ? ADMIN_NAV_ITEMS : [])
  ];
  return items
    .filter(
      (item) => classDeliveryEnabled || item.href !== '/teacher/daily-delivery/'
    )
    .map((item) => {
      const badge = badgeFor(item.href, counts, isSchoolAdmin);
      return badge ? { ...item, ...badge } : { ...item };
    });
}

const ADMIN_ROUTE_PATTERN =
  /^\/teacher\/(settings|teachers|devices|readiness|audit)(?:\/|$)/;

export function isAdminRoute(pathname: string): boolean {
  return ADMIN_ROUTE_PATTERN.test(pathname);
}

export function canAccessTeacherRoute(
  pathname: string,
  isSchoolAdmin: boolean,
  classDeliveryEnabled = false
): boolean {
  if (
    !classDeliveryEnabled &&
    /^\/teacher\/daily-delivery(?:\/|$)/.test(pathname)
  )
    return false;
  return isSchoolAdmin || !isAdminRoute(pathname);
}

export function teacherPageTitle(pathname: string): string {
  if (/^\/teacher\/review\/new\/?$/.test(pathname)) return '日誌の手入力';
  if (/^\/teacher\/review\/[^/]+\/?$/.test(pathname)) return '日誌のレビュー';

  const segment = pathname.replace(/^\/teacher\/?/, '').split('/')[0];
  return (
    {
      '': 'ホーム',
      review: 'レビュー待ち',
      records: '記録履歴',
      notifications: '通知状況',
      'daily-delivery': '今日の配信',
      'audio-jobs': '音声処理状況',
      children: '園児・保護者',
      'voice-consent': '声紋設定',
      settings: '園の設定',
      teachers: '先生管理',
      devices: '録音端末',
      readiness: '稼働準備チェック',
      audit: '操作履歴'
    }[segment] ?? '先生用画面'
  );
}
