import { describe, expect, it, vi } from 'vitest';

import { ApiClient } from '$lib/api';
import { ChildrenService } from './service';

const response = (value: unknown): Response =>
  new Response(JSON.stringify(value), {
    headers: { 'content-type': 'application/json' }
  });

describe('ChildrenService', () => {
  it('退園済みを含む園児と有効な招待メタデータを園単位で取得する', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(response([]))
      .mockResolvedValueOnce(response([]));
    const service = new ChildrenService(new ApiClient({ fetch: fetchMock }));

    await service.listChildren('school/id');
    await service.listInvitations('school/id');

    expect(fetchMock.mock.calls[0][0]).toBe(
      '/api/v1/children?school_id=school%2Fid&include_archived=true'
    );
    expect(fetchMock.mock.calls[1][0]).toBe(
      '/api/v1/line/link-invitations/active?school_id=school%2Fid'
    );
  });

  it('招待コードとアーカイブURLの発行条件をJSONで送る', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockImplementation(async () => response({}));
    const service = new ChildrenService(new ApiClient({ fetch: fetchMock }));

    await service.issueInvitation('child/id');
    await service.issueArchiveLink('child/id');

    expect(fetchMock.mock.calls[0]).toEqual([
      '/api/v1/line/link-invitations',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          child_id: 'child/id',
          expires_in_minutes: 60
        })
      })
    ]);
    expect(fetchMock.mock.calls[1][1]).toEqual(
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ child_id: 'child/id' })
      })
    );
  });

  it('園児IDをURLエンコードしてLINE連携を解除する', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockImplementation(async () => response({}));
    const service = new ChildrenService(new ApiClient({ fetch: fetchMock }));

    await service.unlinkGuardian('child/id');

    expect(fetchMock.mock.calls[0][0]).toBe(
      '/api/v1/children/child%2Fid/guardian-line-link'
    );
    expect(fetchMock.mock.calls[0][1]).toEqual(
      expect.objectContaining({ method: 'DELETE' })
    );
  });
});
