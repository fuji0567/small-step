export type RecordCategory = 'growth' | 'injury';
export type RecordStatus =
  'pending_review' | 'approved' | 'rejected' | 'dispatched';

export interface RecordRead {
  id: string;
  school_id: string;
  teacher_id: string;
  child_id: string | null;
  category: RecordCategory;
  status: RecordStatus;
  source_event_id: string | null;
  confidence: number;
  occurred_at: string;
  summary: string;
  conversation_prompt: string | null;
  anonymized_context: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
}

export type ReadinessStatus = 'ready' | 'not_ready';

export interface RuntimeReadiness {
  status: ReadinessStatus;
  database_ready: boolean;
  database_migration_current: boolean;
  cloud_audio_enabled: boolean;
  cloud_audio_job_storage_ready: boolean | null;
  cloud_audio_llm_configured: boolean | null;
  line_delivery_configured: boolean;
}
