import { describe, expect, it, vi } from 'vitest';

import { ApiClient } from '$lib/api';

import {
  NavigationBadgeService,
  parseNavigationBadgeCounts
} from './navigation-badges';
import { NavigationBadgeState } from './navigation-badges.svelte';

const validCounts = {
  pending_review_records: 1,
  notification_attention: 2,
  failed_audio_jobs: 3,
  invitations_not_issued: 4,
  readiness_issues: 5
};

describe('navigation badges', () => {
  it('APIの全フィールドを非負整数として検証する', () => {
    expect(parseNavigationBadgeCounts(validCounts)).toEqual(validCounts);
  });

  it.each([
    ['null', null],
    ['配列', []],
    ['必須フィールド欠落', { ...validCounts, readiness_issues: undefined }],
    ['null値', { ...validCounts, notification_attention: null }],
    ['負数', { ...validCounts, failed_audio_jobs: -1 }],
    ['小数', { ...validCounts, pending_review_records: 1.5 }],
    ['無限大', { ...validCounts, invitations_not_issued: Infinity }]
  ])('%sを不正応答として弾く', (_label, value) => {
    expect(() => parseNavigationBadgeCounts(value)).toThrow(
      'ナビゲーションバッジの応答が不正です。'
    );
  });

  it('園IDをクエリに含めてcount-only endpointを呼ぶ', async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify(validCounts), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      })
    );
    const service = new NavigationBadgeService(
      new ApiClient({ fetch: fetchMock })
    );

    await expect(service.load('school-1')).resolves.toEqual(validCounts);
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/navigation-badges?school_id=school-1',
      expect.objectContaining({ signal: expect.any(AbortSignal) })
    );
  });

  it('同じ園の初回load重複を共有し、refreshでは再取得する', async () => {
    let finish: ((response: Response) => void) | undefined;
    const fetchMock = vi.fn<typeof fetch>().mockImplementation(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        })
    );
    const state = new NavigationBadgeState(new ApiClient({ fetch: fetchMock }));

    const first = state.load('school-1');
    const second = state.load('school-1');
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    finish?.(
      new Response(JSON.stringify(validCounts), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      })
    );
    await Promise.all([first, second]);
    expect(state.counts).toEqual(validCounts);

    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ ...validCounts, pending_review_records: 9 }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' }
      })
    );
    await state.refresh('school-1');
    expect(state.counts.pending_review_records).toBe(9);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('取得失敗時は既存の件数もすべて非表示にする', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        new Response(JSON.stringify(validCounts), {
          status: 200,
          headers: { 'Content-Type': 'application/json' }
        })
      )
      .mockResolvedValueOnce(new Response('{}', { status: 503 }));
    const state = new NavigationBadgeState(new ApiClient({ fetch: fetchMock }));

    await state.load('school-1');
    await state.refresh('school-1');

    expect(state.counts).toEqual({
      pending_review_records: 0,
      notification_attention: 0,
      failed_audio_jobs: 0,
      invitations_not_issued: 0,
      readiness_issues: 0
    });
  });
});
