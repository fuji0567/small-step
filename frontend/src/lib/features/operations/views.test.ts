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
      fetch: vi
        .fn<typeof fetch>()
        .mockResolvedValueOnce(
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
        .mockResolvedValueOnce(responseJson([]))
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

  it('録音セッションのワーカー待ちと安全なメタデータを描画する', async () => {
    const secretHash = 'a'.repeat(64);
    const internalSessionId = 'session-internal-id';
    const api = new ApiClient({
      fetch: vi
        .fn<typeof fetch>()
        .mockResolvedValueOnce(responseJson([]))
        .mockResolvedValueOnce(
          responseJson([
            {
              id: internalSessionId,
              client_session_id: 'client-session-id',
              status: 'queued',
              segments: [
                {
                  sequence: 0,
                  duration_ms: 4_100,
                  size_bytes: 65_530,
                  sha256: secretHash,
                  media_type: 'audio/webm',
                  created_at: '2026-09-16T05:20:00Z'
                }
              ],
              total_duration_ms: 4_100,
              expires_at: '2026-09-17T05:20:00Z',
              created_at: '2026-09-16T05:20:00Z',
              updated_at: '2026-09-16T05:20:00Z',
              record_id: null,
              audio_processing_incomplete: null
            }
          ])
        )
    });

    render(AudioJobsView, {
      api,
      schoolId: 'school-1',
      controller: new AppController()
    });

    expect(await screen.findByText('ワーカー待ち')).toBeInTheDocument();
    expect(screen.getByText(/00:04/)).toBeInTheDocument();
    expect(screen.getByText(/1セグメント/)).toBeInTheDocument();
    expect(screen.getByText(/65,530バイト/)).toBeInTheDocument();
    expect(document.body.textContent).not.toContain(secretHash);
    expect(document.body.textContent).not.toContain(internalSessionId);
  });

  it('録音セッション取得に失敗してもクラウド音声jobを表示する', async () => {
    const api = new ApiClient({
      fetch: vi
        .fn<typeof fetch>()
        .mockResolvedValueOnce(
          responseJson([
            {
              id: 'job-1',
              school_id: 'school-1',
              teacher_id: 'teacher-1',
              device_id: 'device-1',
              child_id: null,
              status: 'queued',
              attempts: 0,
              record_id: null,
              queued_at: '2026-09-16T05:20:00Z',
              processing_started_at: null,
              completed_at: null,
              expires_at: '2026-09-17T05:20:00Z',
              created_at: '2026-09-16T05:20:00Z',
              updated_at: '2026-09-16T05:20:00Z'
            }
          ])
        )
        .mockResolvedValueOnce(
          new Response(JSON.stringify({ detail: '取得できません' }), {
            status: 503,
            headers: { 'Content-Type': 'application/json' }
          })
        )
    });

    render(AudioJobsView, {
      api,
      schoolId: 'school-1',
      controller: new AppController()
    });

    expect(await screen.findByText('受付済み')).toBeInTheDocument();
    expect(
      await screen.findByText('音声処理状況を取得できませんでした')
    ).toBeInTheDocument();
    expect(screen.getByText(/一部の一覧を表示しています/)).toBeInTheDocument();
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
