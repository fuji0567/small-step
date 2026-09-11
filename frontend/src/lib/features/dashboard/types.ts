import type { ChildRead, LineInvitationRead } from '$lib/features/children';
import type { NotificationOverview } from '$lib/features/notifications';
import type { CloudAudioJob } from '$lib/features/operations';
import type { RecordRead } from '$lib/features/records';

export type DashboardScope =
  'records' | 'notifications' | 'audioJobs' | 'children' | 'invitations';

export interface DashboardData {
  records: RecordRead[];
  notifications: NotificationOverview[];
  audioJobs: CloudAudioJob[];
  children: ChildRead[];
  invitations: LineInvitationRead[];
}

export interface DashboardSummary {
  pendingRecords: number;
  pendingNotifications: number;
  sentNotifications: number;
  notificationWarnings: number;
  activeAudioJobs: number;
  failedAudioJobs: number;
  activeChildren: number;
  unlinkedChildren: number;
  activeInvitations: number;
  invitationsNotIssued: number;
}

export const EMPTY_DASHBOARD_DATA: DashboardData = {
  records: [],
  notifications: [],
  audioJobs: [],
  children: [],
  invitations: []
};
