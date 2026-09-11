import type { RecordCategory, RecordStatus } from './types';
import type { Pathname } from '$app/types';

export function categoryLabel(category: RecordCategory): string {
  return category === 'injury' ? '怪我' : '成長記録';
}

export function statusLabel(status: RecordStatus): string {
  const labels: Record<RecordStatus, string> = {
    pending_review: 'レビュー待ち',
    approved: '承認済み',
    rejected: '却下',
    dispatched: '配信済み'
  };
  return labels[status];
}

export function formatDateTime(value: string | null): string {
  if (!value) return '未設定';
  const date = new Date(value);
  if (!Number.isFinite(date.getTime())) return '日時不明';
  return new Intl.DateTimeFormat('ja-JP', {
    dateStyle: 'medium',
    timeStyle: 'short'
  }).format(date);
}

export function localDateTimeValue(date = new Date()): string {
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

export function dateBoundaryIso(
  value: string,
  boundary: 'start' | 'end'
): string | undefined {
  if (!value) return undefined;
  const suffix = boundary === 'start' ? '00:00:00.000' : '23:59:59.999';
  const date = new Date(`${value}T${suffix}`);
  return Number.isFinite(date.getTime()) ? date.toISOString() : undefined;
}

export function recordDetailPath(recordId: string): Pathname {
  return `/teacher-next/review/${encodeURIComponent(recordId)}/` as Pathname;
}
