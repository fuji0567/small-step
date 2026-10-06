import type { SchoolSummary } from '$lib/state';

export type TeacherRole = 'teacher' | 'school_admin';

export interface TeacherProfile {
  id: string;
  school_id: string;
  name: string;
  email: string | null;
  role: TeacherRole;
  is_auth_linked: boolean;
  is_active: boolean;
  disabled_at: string | null;
  created_at: string;
}

export interface AuthClientConfig {
  auth_mode: 'development' | 'supabase';
  supabase_url: string | null;
  supabase_publishable_key: string | null;
  voiceprint_enabled: boolean;
  teacher_invitations_enabled?: boolean;
  class_delivery_enabled?: boolean;
}

export type TeacherShellPhase =
  'initializing' | 'login' | 'password-setup' | 'bootstrap' | 'ready' | 'fatal';

export interface TeacherShellSnapshot {
  phase: TeacherShellPhase;
  teacher: TeacherProfile | null;
  schools: readonly SchoolSummary[];
  schoolId: string | null;
  isSchoolAdmin: boolean;
}

export interface SupabasePasswordResponse {
  access_token?: unknown;
}
