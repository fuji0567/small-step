import { cleanup, fireEvent, render, screen } from '@testing-library/svelte';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiClient } from '$lib/api';
import { AppController } from '$lib/state';
import VoiceConsentView from './VoiceConsentView.svelte';

let mediaDevicesDescriptor: PropertyDescriptor | undefined;

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    headers: { 'Content-Type': 'application/json' }
  });
}

beforeEach(() => {
  mediaDevicesDescriptor = Object.getOwnPropertyDescriptor(
    navigator,
    'mediaDevices'
  );
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  if (mediaDevicesDescriptor) {
    Object.defineProperty(navigator, 'mediaDevices', mediaDevicesDescriptor);
  } else {
    Reflect.deleteProperty(navigator, 'mediaDevices');
  }
});

describe('VoiceConsentView', () => {
  it('開発モードでは設定変更フォームもAPI呼び出しも出さない', () => {
    const fetchMock = vi.fn<typeof fetch>();

    render(VoiceConsentView, {
      api: new ApiClient({ fetch: fetchMock }),
      enabled: false,
      voiceprintEnabled: false,
      controller: new AppController()
    });

    expect(
      screen.getByText(
        '声紋設定は、Supabaseでログインした先生アカウントでのみ変更できます。'
      )
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '同意を保存' })).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('ログイン済みの先生には未同意状態と保存操作を表示する', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response('null', {
        headers: { 'Content-Type': 'application/json' }
      })
    );

    render(VoiceConsentView, {
      api: new ApiClient({ fetch: fetchMock }),
      enabled: true,
      voiceprintEnabled: false,
      controller: new AppController()
    });

    expect(await screen.findByText('未同意')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: '同意を保存' })
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        '新しい登録と本人確認はできませんが、保存済み声紋の削除や同意の取消はいつでも行えます。'
      )
    ).toBeInTheDocument();
  });

  it('同意済みの先生はブラウザのマイクから録音を開始できる', async () => {
    const trackStop = vi.fn();
    const stream = {
      getTracks: () => [{ stop: trackStop }]
    } as unknown as MediaStream;
    const getUserMedia = vi.fn().mockResolvedValue(stream);
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia }
    });

    class TestMediaRecorder {
      static isTypeSupported(mimeType: string): boolean {
        return mimeType === 'audio/webm;codecs=opus';
      }

      state: RecordingState = 'inactive';
      ondataavailable: ((event: BlobEvent) => void) | null = null;
      onerror: ((event: Event) => void) | null = null;
      onstop: ((event: Event) => void) | null = null;

      start(): void {
        this.state = 'recording';
      }

      stop(): void {
        this.state = 'inactive';
        this.onstop?.(new Event('stop'));
      }
    }
    vi.stubGlobal('MediaRecorder', TestMediaRecorder);

    const consent = {
      id: 'consent-1',
      school_id: 'school-1',
      teacher_id: 'teacher-1',
      purpose: 'speaker-identification',
      policy_version: '1',
      retention_days: 30,
      consented_at: '2026-09-15T00:00:00Z',
      expires_at: '2026-10-15T00:00:00Z',
      revoked_at: null,
      is_active: true,
      created_at: '2026-09-15T00:00:00Z',
      updated_at: '2026-09-15T00:00:00Z'
    };
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockImplementation(async (input) =>
        jsonResponse(String(input).endsWith('/voiceprint/me') ? null : consent)
      );

    render(VoiceConsentView, {
      api: new ApiClient({ fetch: fetchMock }),
      enabled: true,
      voiceprintEnabled: true,
      controller: new AppController()
    });

    const start = await screen.findByRole('button', { name: '録音を開始' });
    await fireEvent.click(start);

    expect(getUserMedia).toHaveBeenCalledWith({
      audio: {
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true
      }
    });
    expect(
      await screen.findByRole('button', { name: '録音を停止' })
    ).toBeInTheDocument();
    expect(screen.getByText('録音中 0秒 / 15秒')).toBeInTheDocument();
  });
});
