import { describe, expect, it, vi } from 'vitest';

import { ApiClient } from '$lib/api';
import { auditParams, OperationsService } from './service';

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' }
  });
}

describe('OperationsService', () => {
  it('音声ではなく安全なジョブ一覧endpointだけを読む', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse([]));
    const service = new OperationsService(new ApiClient({ fetch: fetchMock }));

    await service.listAudioJobs('school-1');

    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      '/api/v1/audio-jobs?school_id=school-1'
    );
  });

  it('録音セッション一覧を学校スコープで読む', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(jsonResponse([]));
    const service = new OperationsService(new ApiClient({ fetch: fetchMock }));

    await service.listRecorderSessions('school-1');

    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      '/api/v1/recorder/sessions?school_id=school-1'
    );
  });

  it('録音機能が無効な404は空一覧として扱う', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(jsonResponse({ detail: 'Not Found' }, 404));
    const service = new OperationsService(new ApiClient({ fetch: fetchMock }));

    await expect(service.listRecorderSessions('school-1')).resolves.toEqual([]);
  });

  it('録音セッションの404以外の失敗は呼び出し元へ返す', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValue(
        jsonResponse({ detail: '一時的に利用できません' }, 503)
      );
    const service = new OperationsService(new ApiClient({ fetch: fetchMock }));

    await expect(
      service.listRecorderSessions('school-1')
    ).rejects.toMatchObject({
      status: 503
    });
  });

  it('readinessの503を診断結果として返す', async () => {
    const payload = {
      status: 'not_ready',
      database_ready: true,
      database_migration_current: false,
      cloud_audio_enabled: false,
      cloud_audio_job_storage_ready: null,
      cloud_audio_llm_configured: null,
      line_delivery_configured: false
    };
    const service = new OperationsService(
      new ApiClient({
        fetch: vi
          .fn<typeof fetch>()
          .mockResolvedValue(jsonResponse(payload, 503))
      })
    );

    await expect(service.readiness()).resolves.toEqual(payload);
  });

  it('監査一覧とCSVで同じ期間条件を使い、CSVではlimitを除く', () => {
    const filters = {
      action: 'record_approved' as const,
      occurredFrom: '2026-09-01',
      occurredTo: '2026-09-02'
    };

    expect(auditParams('school-1', filters).get('limit')).toBe('100');
    expect(auditParams('school-1', filters, false).has('limit')).toBe(false);
    expect(auditParams('school-1', filters).get('occurred_from')).toBe(
      new Date('2026-09-01T00:00:00.000').toISOString()
    );
  });

  it('監査CSVを一覧と同じ絞り込み条件で取得する', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response('実行日時,操作', {
        headers: { 'Content-Type': 'text/csv; charset=utf-8' }
      })
    );
    const service = new OperationsService(new ApiClient({ fetch: fetchMock }));

    await service.exportAuditEvents('school-1', {
      action: 'record_approved',
      occurredFrom: '',
      occurredTo: ''
    });

    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      '/api/v1/audit-events/export.csv?school_id=school-1&action=record_approved'
    );
    expect(
      new Headers(fetchMock.mock.calls[0]?.[1]?.headers).get('Accept')
    ).toBe('text/csv');
  });
});
