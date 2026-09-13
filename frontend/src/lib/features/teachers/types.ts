export type TeacherRole = 'teacher' | 'school_admin';

export interface TeacherRead {
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

export type TeacherConfirmation =
  | { kind: 'disable'; teacher: TeacherRead }
  | { kind: 'restore'; teacher: TeacherRead }
  | { kind: 'role'; teacher: TeacherRead; nextRole: TeacherRole };
