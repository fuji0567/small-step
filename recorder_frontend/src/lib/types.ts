export type RecorderView =
  | "login"
  | "ready"
  | "recording"
  | "paused"
  | "stopped"
  | "unsent"
  | "accepted";

export interface RecorderSegment {
  sequence: number;
  blob: Blob;
  durationMs: number;
  sha256?: string;
}

export interface LocalRecordingSession {
  demoTraceRequested?: boolean;
  clientSessionId: string;
  serverSessionId: string | null;
  ownerId: string;
  createdAt: number;
  updatedAt: number;
  status: "recording" | "stopped" | "uploading" | "pending";
  mimeType: string;
  durationMs: number;
  segments: RecorderSegment[];
}

export interface ServerSegment {
  sequence: number;
  duration_ms: number;
  size_bytes: number;
  sha256: string;
  media_type: string;
}

export interface ServerRecordingSession {
  id: string;
  client_session_id: string;
  status: string;
  segments: ServerSegment[];
  total_duration_ms: number;
  created_at?: string;
  updated_at?: string;
  processed_segment_count?: number;
  failed_segment_count?: number;
  record_id?: string | null;
  audio_processing_incomplete?: boolean | null;
  [key: string]: unknown;
}

export interface AuthConfig {
  recorder_demo_trace_enabled?: boolean;
  auth_mode: "development" | "supabase";
  supabase_url: string | null;
  supabase_publishable_key: string | null;
}

export interface RecorderDemo {
  outcome:
    "waiting" | "unavailable" | "record_created" | "no_record" | "failed";
  expires_at?: number;
  record_id?: string | null;
  truncated?: boolean;
  events: { phase: string; kind: string; text: string; truncated: boolean }[];
}

export interface AuthenticatedTeacher {
  id: string;
  name: string;
  role: "teacher" | "school_admin";
  trial_mode?: boolean;
  [key: string]: unknown;
}
