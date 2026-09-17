export interface ChildRead {
  id: string;
  school_id: string;
  display_name: string;
  recording_names?: string[];
  guardian_line_user_id: string | null;
  is_active: boolean;
  archived_at: string | null;
  created_at: string;
}

export interface LineInvitationRead {
  id: string;
  school_id: string;
  child_id: string;
  expires_at: string;
  used_at: string | null;
  revoked_at: string | null;
  created_at: string;
}

export interface LineInvitationCredential extends LineInvitationRead {
  invite_code: string;
}

export interface GuardianArchiveCredential {
  id: string;
  school_id: string;
  child_id: string;
  expires_at: string;
  revoked_at: string | null;
  created_at: string;
  archive_url: string;
}

export type ChildConfirmation =
  | { kind: 'archive'; child: ChildRead }
  | { kind: 'restore'; child: ChildRead }
  | { kind: 'unlink'; child: ChildRead }
  | { kind: 'invitation'; child: ChildRead; replacing: boolean }
  | { kind: 'archive-link'; child: ChildRead };
