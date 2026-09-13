import { cleanup, render, screen } from '@testing-library/svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiClient } from '$lib/api';
import { AppController } from '$lib/state';
import AuditEventsView from './AuditEventsView.svelte';
import AudioJobsView from './AudioJobsView.svelte';
import ReadinessView from './ReadinessView.svelte';

function responseJson(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' }
  });
}

afterEach(cleanup);

describe('operations views', () => {
  it('音声jobは安全な状態だけを描画し、保存先や文字起こしを出さない', async () => {
    const secret = 'private/audio.wav';
    const api = new ApiClient({
      fetch: vi.fn<typeof fetch>().mockResolvedValue(
        responseJson([
          {
            id: 'job-1',
            school_id: 'school-1',
            teacher_id: 'teacher-1',
            device_id: 'device-1',
            child_id: null,
            status: 'failed',
            attempts: 2,
            record_id: null,
            queued_at: '2026-09-11T08:00:00Z',
            processing_started_at: null,
            completed_at: null,
            expires_at: '2026-09-11T09:00:00Z',
            created_at: '2026-09-11T08:00:00Z',
            updated_at: '2026-09-11T08:00:00Z',
            raw_audio_path: secret,
            transcript: '表示禁止'
          }
        ])
      )
    });

    render(AudioJobsView, {
      api,
      schoolId: 'school-1',
      controller: new AppController()
    });

    expect(await screen.findByText('処理失敗')).toBeInTheDocument();
    expect(document.body.textContent).not.toContain(secret);
    expect(document.body.textContent).not.toContain('表示禁止');
  });

  it('503 readinessをエラーではなく要確認の診断として表示する', async () => {
    const api = new ApiClient({
      fetch: vi.fn<typeof fetch>().mockResolvedValue(
        responseJson(
          {
            status: 'not_ready',
            database_ready: true,
            database_migration_current: false,
            cloud_audio_enabled: false,
            cloud_audio_job_storage_ready: null,
            cloud_audio_llm_configured: null,
            line_delivery_configured: false
          },
          503
        )
      )
    });

    render(ReadinessView, {
      api,
      isSchoolAdmin: true,
      controller: new AppController()
    });

    expect(await screen.findByText('更新が必要')).toBeInTheDocument();
    expect(screen.queryByText('稼働準備を確認できませんでした')).toBeNull();
  });

  it('一般の先生のreadinessではAPIを呼ばない', () => {
    const fetchMock = vi.fn<typeof fetch>();
    render(ReadinessView, {
      api: new ApiClient({ fetch: fetchMock }),
      isSchoolAdmin: false,
      controller: new AppController()
    });

    expect(
      screen.getByText('この画面を利用する権限がありません。')
    ).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('一般の先生の監査画面にはCSV操作を出さずAPIも呼ばない', () => {
    const fetchMock = vi.fn<typeof fetch>();
    render(AuditEventsView, {
      api: new ApiClient({ fetch: fetchMock }),
      schoolId: 'school-1',
      isSchoolAdmin: false,
      controller: new AppController()
    });

    expect(
      screen.queryByRole('button', { name: 'CSVをダウンロード' })
    ).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
