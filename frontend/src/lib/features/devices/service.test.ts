import { describe, expect, it, vi } from 'vitest';

import { ApiClient } from '$lib/api';
import { DevicesService } from './service';

const response = (value: unknown): Response =>
  new Response(JSON.stringify(value), {
    headers: { 'content-type': 'application/json' }
  });

describe('DevicesService', () => {
  it('端末と先生を同じ園スコープで取得する', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(response([]))
      .mockResolvedValueOnce(response([]));
    const service = new DevicesService(new ApiClient({ fetch: fetchMock }));

    await service.listDevices('school/id');
    await service.listTeachers('school/id');

    expect(fetchMock.mock.calls[0][0]).toBe(
      '/api/v1/edge-devices?school_id=school%2Fid'
    );
    expect(fetchMock.mock.calls[1][0]).toBe(
      '/api/v1/teachers?school_id=school%2Fid'
    );
  });

  it('端末登録と鍵再発行を型付きAPIへ送る', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockImplementation(async () => response({}));
    const service = new DevicesService(new ApiClient({ fetch: fetchMock }));

    await service.create('school-id', 'teacher-id', '胸元端末');
    await service.rotate('device/id');

    expect(fetchMock.mock.calls[0][1]).toEqual(
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          school_id: 'school-id',
          teacher_id: 'teacher-id',
          name: '胸元端末'
        })
      })
    );
    expect(fetchMock.mock.calls[1][0]).toBe(
      '/api/v1/edge-devices/device%2Fid/rotate-key'
    );
  });
});
