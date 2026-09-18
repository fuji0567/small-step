import { ApiClient, ApiInvalidResponseError } from '$lib/api';

import type { TeacherRead, TeacherRole } from './types';

function required<T>(value: T | null): T {
  if (value === null) throw new ApiInvalidResponseError();
  return value;
}

export class TeachersService {
  constructor(private readonly client: ApiClient) {}

  async list(schoolId: string, signal?: AbortSignal): Promise<TeacherRead[]> {
    const params = new URLSearchParams({ school_id: schoolId });
    return required(
      await this.client.requestJson<TeacherRead[]>(`teachers?${params}`, {
        signal
      })
    );
  }

  async create(
    schoolId: string,
    name: string,
    email: string
  ): Promise<TeacherRead> {
    return required(
      await this.client.requestJson<TeacherRead>('teachers', {
        method: 'POST',
        json: { school_id: schoolId, name, email, role: 'teacher' }
      })
    );
  }

  async changeRole(teacherId: string, role: TeacherRole): Promise<TeacherRead> {
    return required(
      await this.client.requestJson<TeacherRead>(
        `teachers/${encodeURIComponent(teacherId)}/role`,
        { method: 'PATCH', json: { role } }
      )
    );
  }

  async disable(teacherId: string): Promise<TeacherRead> {
    return this.postAction(teacherId, 'disable');
  }

  async restore(teacherId: string): Promise<TeacherRead> {
    return this.postAction(teacherId, 'restore');
  }

  async invite(teacherId: string): Promise<TeacherRead> {
    return required(
      await this.client.requestJson<TeacherRead>(
        `teachers/${encodeURIComponent(teacherId)}/invite`,
        { method: 'POST' }
      )
    );
  }

  private async postAction(
    teacherId: string,
    action: 'disable' | 'restore'
  ): Promise<TeacherRead> {
    return required(
      await this.client.requestJson<TeacherRead>(
        `teachers/${encodeURIComponent(teacherId)}/${action}`,
        { method: 'POST' }
      )
    );
  }
}
