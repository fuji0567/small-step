import type { ApiClient } from '$lib/api';
import { ChildrenService } from '$lib/features/children';
import { NotificationsService } from '$lib/features/notifications';
import { OperationsService } from '$lib/features/operations';
import { RecordsService } from '$lib/features/records';

import type { DashboardData, DashboardScope, DashboardSummary } from './types';

export class DashboardService {
  readonly #records: RecordsService;
  readonly #notifications: NotificationsService;
  readonly #operations: OperationsService;
  readonly #children: ChildrenService;

  constructor(api: ApiClient) {
    this.#records = new RecordsService(api);
    this.#notifications = new NotificationsService(api);
    this.#operations = new OperationsService(api);
    this.#children = new ChildrenService(api);
  }

  load(
    scope: DashboardScope,
    schoolId: string,
    signal: AbortSignal,
    isSchoolAdmin: boolean
  ): Promise<DashboardData[DashboardScope]> {
    switch (scope) {
      case 'records':
        return this.#records.listPending(schoolId, signal);
      case 'notifications':
        return this.#notifications.list(schoolId, '', signal);
      case 'audioJobs':
        return this.#operations.listAudioJobs(schoolId, signal);
      case 'children':
        return this.#children.listChildren(schoolId, signal);
      case 'invitations':
        return isSchoolAdmin
          ? this.#children.listInvitations(schoolId, signal)
          : Promise.resolve([]);
    }
  }
}

export function summarizeDashboard(data: DashboardData): DashboardSummary {
  const activeChildren = data.children.filter((child) => child.is_active);
  const invitedChildIds = new Set(
    data.invitations.map((invitation) => invitation.child_id)
  );
  const unlinkedChildren = activeChildren.filter(
    (child) => !child.guardian_line_user_id
  );

  return {
    pendingRecords: data.records.length,
    pendingNotifications: data.notifications.filter(
      (notification) => notification.status === 'pending'
    ).length,
    sentNotifications: data.notifications.filter(
      (notification) => notification.status === 'sent'
    ).length,
    notificationWarnings: data.notifications.filter((notification) =>
      ['failed', 'waiting_guardian_link'].includes(notification.status)
    ).length,
    activeAudioJobs: data.audioJobs.filter((job) =>
      ['queued', 'processing'].includes(job.status)
    ).length,
    failedAudioJobs: data.audioJobs.filter((job) => job.status === 'failed')
      .length,
    activeChildren: activeChildren.length,
    unlinkedChildren: unlinkedChildren.length,
    activeInvitations: data.invitations.length,
    invitationsNotIssued: unlinkedChildren.filter(
      (child) => !invitedChildIds.has(child.id)
    ).length
  };
}
