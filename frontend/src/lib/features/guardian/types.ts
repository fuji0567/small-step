export type GuardianArchiveCategory = 'growth' | 'injury';

export interface GuardianArchiveNotification {
  delivered_at: string;
  category: GuardianArchiveCategory;
  summary: string;
  conversation_prompt: string | null;
}

export interface GuardianArchive {
  child_display_name: string;
  expires_at: string;
  notifications: GuardianArchiveNotification[];
}

export type GuardianArchiveLoadResult =
  | { status: 'success'; archive: GuardianArchive }
  | { status: 'invalid-link' }
  | { status: 'network-error' }
  | { status: 'cancelled' };
