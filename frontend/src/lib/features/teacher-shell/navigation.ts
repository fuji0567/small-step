import type { AppShellNavItem } from '$lib/components';

export const TEACHER_NAV_ITEMS = [
  { href: '/teacher/', label: 'ホーム', icon: 'home' },
  { href: '/teacher/review/', label: 'レビュー待ち', icon: 'review' },
  { href: '/teacher/records/', label: '記録履歴', icon: 'history' },
  {
    href: '/teacher/notifications/',
    label: '通知状況',
    icon: 'notifications'
  },
  {
    href: '/teacher/audio-jobs/',
    label: '音声処理状況',
    icon: 'audio'
  },
  { href: '/teacher/children/', label: '園児・保護者', icon: 'child' },
  {
    href: '/teacher/voice-consent/',
    label: '声紋設定',
    icon: 'microphone'
  }
] as const satisfies readonly AppShellNavItem[];

export const ADMIN_NAV_ITEMS = [
  { href: '/teacher/settings/', label: '園の設定', icon: 'schedule' },
  { href: '/teacher/teachers/', label: '先生管理', icon: 'group' },
  { href: '/teacher/devices/', label: '録音端末', icon: 'microphone' },
  {
    href: '/teacher/readiness/',
    label: '稼働準備チェック',
    icon: 'checklist'
  },
  { href: '/teacher/audit/', label: '操作履歴', icon: 'privacy' }
] as const satisfies readonly AppShellNavItem[];

export function teacherNavItems(isSchoolAdmin: boolean): AppShellNavItem[] {
  return [...TEACHER_NAV_ITEMS, ...(isSchoolAdmin ? ADMIN_NAV_ITEMS : [])];
}

const ADMIN_ROUTE_PATTERN =
  /^\/teacher\/(settings|teachers|devices|readiness|audit)(?:\/|$)/;

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
  if (/^\/teacher\/review\/new\/?$/.test(pathname)) return '日誌の手入力';
  if (/^\/teacher\/review\/[^/]+\/?$/.test(pathname)) return '日誌のレビュー';

  const segment = pathname.replace(/^\/teacher\/?/, '').split('/')[0];
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
