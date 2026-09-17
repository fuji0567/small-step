import type { RecordCategory } from '$lib/api';

export type NotificationStatus =
  | 'pending'
  | 'waiting_guardian_link'
  | 'sent'
  | 'failed'
  | 'cancelled'
  | 'trial';

export interface NotificationOverview {
  id: string;
  record_id: string;
  channel: string;
  scheduled_for: string;
  status: NotificationStatus;
  delivery_attempts: number;
  last_attempt_at: string | null;
  last_failure_kind: string | null;
  sent_at: string | null;
  created_at: string;
  child_id: string | null;
  child_display_name: string | null;
  category: RecordCategory;
  summary: string;
  notion_synced_at: string | null;
  notion_page_url: string | null;
}

export interface NotificationUpdate {
  id: string;
  record_id: string;
  scheduled_for: string;
  status: NotificationStatus;
}

export interface NotificationFilters {
  status: NotificationStatus | '';
  search: string;
}
