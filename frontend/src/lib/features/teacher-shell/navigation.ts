import type { AppShellNavItem } from '$lib/components';

export const TEACHER_NAV_ITEMS = [
  { href: '/teacher-next/', label: 'ホーム', icon: 'home' },
  { href: '/teacher-next/review/', label: 'レビュー待ち', icon: 'review' },
  { href: '/teacher-next/records/', label: '記録履歴', icon: 'history' },
  {
    href: '/teacher-next/notifications/',
    label: '通知状況',
    icon: 'notifications'
  },
  {
    href: '/teacher-next/audio-jobs/',
    label: '音声処理状況',
    icon: 'audio'
  },
  { href: '/teacher-next/children/', label: '園児・保護者', icon: 'child' },
  {
    href: '/teacher-next/voice-consent/',
    label: '声紋設定',
    icon: 'microphone'
  }
] as const satisfies readonly AppShellNavItem[];

export const ADMIN_NAV_ITEMS = [
  { href: '/teacher-next/settings/', label: '園の設定', icon: 'schedule' },
  { href: '/teacher-next/teachers/', label: '先生管理', icon: 'group' },
  { href: '/teacher-next/devices/', label: '録音端末', icon: 'microphone' },
  {
    href: '/teacher-next/readiness/',
    label: '稼働準備チェック',
    icon: 'checklist'
  },
  { href: '/teacher-next/audit/', label: '操作履歴', icon: 'privacy' }
] as const satisfies readonly AppShellNavItem[];

export function teacherNavItems(isSchoolAdmin: boolean): AppShellNavItem[] {
  return [...TEACHER_NAV_ITEMS, ...(isSchoolAdmin ? ADMIN_NAV_ITEMS : [])];
}

const ADMIN_ROUTE_PATTERN =
  /^\/teacher-next\/(settings|teachers|devices|readiness|audit)(?:\/|$)/;

export function isAdminRoute(pathname: string): boolean {
  return ADMIN_ROUTE_PATTERN.test(pathname);
}

export function canAccessTeacherRoute(
  pathname: string,
  isSchoolAdmin: boolean
): boolean {
  return isSchoolAdmin || !isAdminRoute(pathname);
}

export function teacherPageTitle(pathname: string): string {
  if (/^\/teacher-next\/review\/new\/?$/.test(pathname)) return '日誌の手入力';
  if (/^\/teacher-next\/review\/[^/]+\/?$/.test(pathname))
    return '日誌のレビュー';

  const segment = pathname.replace(/^\/teacher-next\/?/, '').split('/')[0];
  return (
    {
      '': 'ホーム',
      review: 'レビュー待ち',
      records: '記録履歴',
      notifications: '通知状況',
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
