import { ApiClient, ApiInvalidResponseError } from '$lib/api';

import type {
  ChildRead,
  GuardianArchiveCredential,
  LineInvitationCredential,
  LineInvitationRead
} from './types';

function required<T>(value: T | null): T {
  if (value === null) throw new ApiInvalidResponseError();
  return value;
}

export class ChildrenService {
  constructor(private readonly client: ApiClient) {}

  async listChildren(
    schoolId: string,
    signal?: AbortSignal
  ): Promise<ChildRead[]> {
    const params = new URLSearchParams({
      school_id: schoolId,
      include_archived: 'true'
    });
    return required(
      await this.client.requestJson<ChildRead[]>(`children?${params}`, {
        signal
      })
    );
  }

  async listInvitations(
    schoolId: string,
    signal?: AbortSignal
  ): Promise<LineInvitationRead[]> {
    const params = new URLSearchParams({ school_id: schoolId });
    return required(
      await this.client.requestJson<LineInvitationRead[]>(
        `line/link-invitations/active?${params}`,
        { signal }
      )
    );
  }

  async create(schoolId: string, displayName: string): Promise<ChildRead> {
    return required(
      await this.client.requestJson<ChildRead>('children', {
        method: 'POST',
        json: { school_id: schoolId, display_name: displayName }
      })
    );
  }

  async rename(childId: string, displayName: string): Promise<ChildRead> {
    return required(
      await this.client.requestJson<ChildRead>(
        `children/${encodeURIComponent(childId)}`,
        { method: 'PATCH', json: { display_name: displayName } }
      )
    );
  }

  async archive(childId: string): Promise<ChildRead> {
    return this.postChildAction(childId, 'archive');
  }

  async restore(childId: string): Promise<ChildRead> {
    return this.postChildAction(childId, 'restore');
  }

  async unlinkGuardian(childId: string): Promise<ChildRead> {
    return required(
      await this.client.requestJson<ChildRead>(
        `children/${encodeURIComponent(childId)}/guardian-line-link`,
        { method: 'DELETE' }
      )
    );
  }

  async issueInvitation(childId: string): Promise<LineInvitationCredential> {
    return required(
      await this.client.requestJson<LineInvitationCredential>(
        'line/link-invitations',
        {
          method: 'POST',
          json: { child_id: childId, expires_in_minutes: 60 }
        }
      )
    );
  }

  async issueArchiveLink(childId: string): Promise<GuardianArchiveCredential> {
    return required(
      await this.client.requestJson<GuardianArchiveCredential>(
        'guardian-archive-links',
        { method: 'POST', json: { child_id: childId } }
      )
    );
  }

  async postChildAction(
    childId: string,
    action: 'archive' | 'restore'
  ): Promise<ChildRead> {
    return required(
      await this.client.requestJson<ChildRead>(
        `children/${encodeURIComponent(childId)}/${action}`,
        { method: 'POST' }
      )
    );
  }
}
