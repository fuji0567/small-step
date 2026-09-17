import type {
  AuditEventAction,
  CloudAudioJobStatus,
  RecorderSession,
  RecorderSessionStatus
} from './types';

export function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat('ja-JP', {
    dateStyle: 'medium',
    timeStyle: 'short'
  }).format(new Date(value));
}

export function audioStatusLabel(status: CloudAudioJobStatus): string {
  return {
    queued: '受付済み',
    processing: 'GPU処理中',
    completed: '記録作成済み',
    failed: '処理失敗',
    expired: '期限切れ'
  }[status];
}

export function audioDescription(status: CloudAudioJobStatus): string {
  return {
    queued: 'GPUワーカーの処理待ちです。',
    processing: 'GPUワーカーが音声を解析しています。',
    completed: 'レビュー待ちの記録を作成しました。',
    failed:
      '音声は削除済みです。録音設定を確認して、もう一度送信してください。',
    expired: '時間内に処理されなかったため、音声を削除しました。'
  }[status];
}

export function recorderStatusLabel(status: RecorderSessionStatus): string {
  return {
    draft: '送信前',
    queued: 'ワーカー待ち',
    processing: '処理中',
    completed: '記録作成済み',
    failed: '処理失敗',
    discarded: '破棄済み',
    expired: '期限切れ'
  }[status];
}

export function recorderDescription(status: RecorderSessionStatus): string {
  return {
    draft: '録音の送信がまだ確定していません。',
    queued: '録音を処理するワーカーの作業待ちです。',
    processing: '録音を処理しています。',
    completed: 'レビュー待ちの記録を作成しました。',
    failed: '録音の処理に失敗しました。設定を確認してください。',
    discarded: '録音は破棄されています。',
    expired: '期限を過ぎたため、録音を処理できませんでした。'
  }[status];
}

export function recorderTone(status: RecorderSessionStatus) {
  if (status === 'completed') return 'success' as const;
  if (status === 'failed') return 'error' as const;
  if (status === 'processing') return 'info' as const;
  if (status === 'expired') return 'warning' as const;
  return 'neutral' as const;
}

export function recorderDuration(session: RecorderSession): string {
  const totalSeconds = Math.max(
    0,
    Math.floor(session.total_duration_ms / 1000)
  );
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
}

export function recorderSize(session: RecorderSession): string {
  const totalBytes = session.segments.reduce(
    (sum, segment) => sum + Math.max(0, segment.size_bytes),
    0
  );
  return `${new Intl.NumberFormat('ja-JP').format(totalBytes)}バイト`;
}

export const AUDIT_ACTION_LABELS: Record<AuditEventAction, string> = {
  line_link_invitation_issued: '保護者LINEの招待コードを発行',
  guardian_line_linked: '保護者LINEが連携済みになりました',
  guardian_line_unlinked: '保護者LINEの連携を解除',
  guardian_archive_issued: '配信アーカイブURLを発行',
  guardian_archive_revoked: '配信アーカイブURLを無効化',
  record_reassigned: '記録の担当先生を変更',
  record_approved: '記録を承認',
  record_rejected: '記録を却下',
  notification_retry_scheduled: 'LINE通知の再送を予約',
  notification_cancelled: 'LINE通知を取消',
  notification_rescheduled: 'LINE通知の配信日時を変更',
  child_updated: '園児の表示名を変更',
  child_archived: '園児を退園処理',
  child_restored: '園児を復園へ戻す',
  teacher_disabled: '先生アカウントを利用停止',
  teacher_restored: '先生アカウントの利用を再開',
  teacher_role_changed: '先生の権限を変更',
  school_digest_time_changed: '成長記録の配信時刻を変更',
  school_trial_mode_changed: '試用モードを変更',
  manual_record_created: '手入力の記録を作成',
  record_history_exported: '記録履歴をCSV出力',
  audit_history_exported: '操作履歴をCSV出力',
  notion_synced: 'Notionに記録',
  edge_device_created: '録音端末を登録',
  edge_device_key_rotated: '録音端末のキーを再発行',
  edge_device_disabled: '録音端末を無効化'
};
