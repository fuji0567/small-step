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
