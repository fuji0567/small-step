export type CloudAudioJobStatus =
  'queued' | 'processing' | 'completed' | 'failed' | 'expired';

/** APIが公開する安全なメタデータだけ。音声・文字起こし・保存先は含めない。 */
export interface CloudAudioJob {
  id: string;
  school_id: string;
  teacher_id: string;
  device_id: string;
  child_id: string | null;
  status: CloudAudioJobStatus;
  attempts: number;
  record_id: string | null;
  queued_at: string;
  processing_started_at: string | null;
  completed_at: string | null;
  expires_at: string;
  created_at: string;
  updated_at: string;
}

export type AuditEventAction =
  | 'line_link_invitation_issued'
  | 'guardian_line_linked'
  | 'guardian_line_unlinked'
  | 'guardian_archive_issued'
  | 'guardian_archive_revoked'
  | 'record_approved'
  | 'record_rejected'
  | 'notification_retry_scheduled'
  | 'notification_cancelled'
  | 'notification_rescheduled'
  | 'child_updated'
  | 'child_archived'
  | 'child_restored'
  | 'teacher_disabled'
  | 'teacher_restored'
  | 'teacher_role_changed'
  | 'school_digest_time_changed'
  | 'manual_record_created'
  | 'record_history_exported'
  | 'audit_history_exported'
  | 'notion_synced'
  | 'edge_device_created'
  | 'edge_device_key_rotated'
  | 'edge_device_disabled';

export interface AuditEvent {
  action: AuditEventAction;
  target_type: string;
  actor_display_name: string | null;
  created_at: string;
}

export interface AuditFilters {
  action: AuditEventAction | '';
  occurredFrom: string;
  occurredTo: string;
}
