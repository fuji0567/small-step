export interface EdgeDeviceRead {
  id: string;
  school_id: string;
  teacher_id: string;
  name: string;
  is_active: boolean;
  last_seen_at: string | null;
  created_at: string;
}

export interface EdgeDeviceCredential extends EdgeDeviceRead {
  api_key: string;
}

export interface DeviceTeacher {
  id: string;
  name: string;
  is_active: boolean;
}

export type DeviceConfirmation =
  | { kind: 'rotate'; device: EdgeDeviceRead }
  | { kind: 'disable'; device: EdgeDeviceRead };
