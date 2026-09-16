export interface VoiceConsent {
  id: string;
  school_id: string;
  teacher_id: string;
  purpose: string;
  policy_version: string;
  retention_days: number;
  consented_at: string;
  expires_at: string;
  revoked_at: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Voiceprint {
  id: string;
  school_id: string;
  teacher_id: string;
  model_name: string;
  sample_count: number;
  enrolled_at: string;
  expires_at: string;
  created_at: string;
  updated_at: string;
}

export type VoiceprintJobKind = 'enrollment' | 'verification';
export type VoiceprintJobStatus =
  'queued' | 'processing' | 'completed' | 'failed' | 'expired';
export type VoiceprintQualityIssue =
  | 'too_short'
  | 'too_long'
  | 'too_quiet'
  | 'too_noisy'
  | 'clipping'
  | 'multiple_speakers'
  | 'invalid_audio';

export interface VoiceprintJob {
  id: string;
  school_id: string;
  teacher_id: string;
  kind: VoiceprintJobKind;
  status: VoiceprintJobStatus;
  attempts: number;
  similarity_score: number | null;
  matched: boolean | null;
  quality_issue: VoiceprintQualityIssue | null;
  quality_sample_index: number | null;
  queued_at: string;
  processing_started_at: string | null;
  completed_at: string | null;
  expires_at: string;
  created_at: string;
  updated_at: string;
}
