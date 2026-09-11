import type { RecordCategory, RecordRead, RecordStatus } from '$lib/api';

export type { RecordCategory, RecordRead, RecordStatus };

export interface RecordChild {
  id: string;
  school_id: string;
  display_name: string;
  guardian_line_user_id: string | null;
  is_active: boolean;
  archived_at: string | null;
  created_at: string;
}

export interface RecordTeacher {
  id: string;
  name: string;
  is_active: boolean;
}

export interface ManualRecordInput {
  school_id: string;
  teacher_id?: string;
  child_id: string;
  category: RecordCategory;
  occurred_at: string;
  summary: string;
  conversation_prompt?: string;
}

export interface RecordReviewInput {
  child_id?: string;
  summary?: string;
  conversation_prompt?: string;
  scheduled_for?: string;
}

export interface RecordHistoryFilters {
  search?: string;
  childId?: string;
  status?: RecordStatus | '';
  category?: RecordCategory | '';
  occurredFrom?: string;
  occurredTo?: string;
  limit?: number;
}
