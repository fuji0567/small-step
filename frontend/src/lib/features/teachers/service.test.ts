import { describe, expect, it, vi } from 'vitest';

import { ApiClient } from '$lib/api';
import { TeachersService } from './service';

const response = (value: unknown): Response =>
  new Response(JSON.stringify(value), {
    headers: { 'content-type': 'application/json' }
  });

describe('TeachersService', () => {
  it('先生は常に通常権限で事前登録する', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockImplementation(async () => response({}));
    const service = new TeachersService(new ApiClient({ fetch: fetchMock }));

    await service.create('school-id', '山田', 'YAMADA@example.com');

    expect(fetchMock.mock.calls[0][1]).toEqual(
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          school_id: 'school-id',
          name: '山田',
          email: 'YAMADA@example.com',
          role: 'teacher'
        })
      })
    );
  });

  it('役割変更と利用停止の対象IDをURLエンコードする', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockImplementation(async () => response({}));
    const service = new TeachersService(new ApiClient({ fetch: fetchMock }));

    await service.changeRole('teacher/id', 'school_admin');
    await service.disable('teacher/id');

    expect(fetchMock.mock.calls[0][0]).toBe(
      '/api/v1/teachers/teacher%2Fid/role'
    );
    expect(fetchMock.mock.calls[1][0]).toBe(
      '/api/v1/teachers/teacher%2Fid/disable'
    );
  });
});
