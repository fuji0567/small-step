import { ApiClient, ApiInvalidResponseError } from '$lib/api';

import type {
  DeviceTeacher,
  EdgeDeviceCredential,
  EdgeDeviceRead
} from './types';

function required<T>(value: T | null): T {
  if (value === null) throw new ApiInvalidResponseError();
  return value;
}

export class DevicesService {
  constructor(private readonly client: ApiClient) {}

  async listDevices(
    schoolId: string,
    signal?: AbortSignal
  ): Promise<EdgeDeviceRead[]> {
    const params = new URLSearchParams({ school_id: schoolId });
    return required(
      await this.client.requestJson<EdgeDeviceRead[]>(
        `edge-devices?${params}`,
        { signal }
      )
    );
  }

  async listTeachers(
    schoolId: string,
    signal?: AbortSignal
  ): Promise<DeviceTeacher[]> {
    const params = new URLSearchParams({ school_id: schoolId });
    return required(
      await this.client.requestJson<DeviceTeacher[]>(`teachers?${params}`, {
        signal
      })
    );
  }

  async create(
    schoolId: string,
    teacherId: string,
    name: string
  ): Promise<EdgeDeviceCredential> {
    return required(
      await this.client.requestJson<EdgeDeviceCredential>('edge-devices', {
        method: 'POST',
        json: { school_id: schoolId, teacher_id: teacherId, name }
      })
    );
  }

  async rotate(deviceId: string): Promise<EdgeDeviceCredential> {
    return required(
      await this.client.requestJson<EdgeDeviceCredential>(
        `edge-devices/${encodeURIComponent(deviceId)}/rotate-key`,
        { method: 'POST' }
      )
    );
  }

  async disable(deviceId: string): Promise<EdgeDeviceRead> {
    return required(
      await this.client.requestJson<EdgeDeviceRead>(
        `edge-devices/${encodeURIComponent(deviceId)}/disable`,
        { method: 'POST' }
      )
    );
  }
}
