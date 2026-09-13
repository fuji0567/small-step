import { describe, expect, it, vi } from 'vitest';

import { ApiClient } from './client';
import {
  ApiHttpError,
  ApiInvalidResponseError,
  ApiRequestCancelledError,
  ApiTimeoutError,
  GENERIC_API_ERROR_MESSAGE
} from './errors';
import { getRuntimeReadiness } from './readiness';

function responseJson(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    ...init,
    headers: { 'content-type': 'application/json', ...init.headers }
  });
}

function abortableFetch(): typeof fetch {
  return vi.fn<typeof fetch>((_input, init) => {
    return new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener(
        'abort',
        () =>
          reject(
            init.signal?.reason ?? new DOMException('Aborted', 'AbortError')
          ),
        { once: true }
      );
    });
  });
}

describe('ApiClient', () => {
  it('同一originのAPI prefixを使い、tokenがある場合だけBearerを付ける', async () => {
    const authenticatedFetch = vi.fn<typeof fetch>(async () =>
      responseJson({ ok: true })
    );
    const authenticated = new ApiClient({
      accessToken: () => 'secret-token',
      fetch: authenticatedFetch
    });

    await authenticated.requestJson('/records');

    expect(authenticatedFetch).toHaveBeenCalledOnce();
    expect(authenticatedFetch.mock.calls[0][0]).toBe('/api/v1/records');
    expect(
      new Headers(authenticatedFetch.mock.calls[0][1]?.headers).get(
        'Authorization'
      )
    ).toBe('Bearer secret-token');

    const anonymousFetch = vi.fn<typeof fetch>(async () =>
      responseJson({ ok: true })
    );
    const anonymous = new ApiClient({ fetch: anonymousFetch });
    await anonymous.requestJson('/records', {
      headers: { Authorization: 'Bearer caller-must-not-inject' }
    });

    expect(
      new Headers(anonymousFetch.mock.calls[0][1]?.headers).has('Authorization')
    ).toBe(false);
  });

  it('absolute URLとprotocol-relative URLを拒否する', async () => {
    const fetchMock = vi.fn<typeof fetch>(async () =>
      responseJson({ ok: true })
    );
    const client = new ApiClient({ fetch: fetchMock });

    await expect(
      client.requestJson('https://example.test/api')
    ).rejects.toThrow(TypeError);
    await expect(client.requestJson('//example.test/api')).rejects.toThrow(
      TypeError
    );
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('204をnullとして扱い、JSON・text・blobを用途別に読む', async () => {
    const noContent = new ApiClient({
      fetch: vi.fn<typeof fetch>(
        async () => new Response(null, { status: 204 })
      )
    });
    await expect(noContent.requestJson('/empty')).resolves.toBeNull();

    const json = new ApiClient({
      fetch: vi.fn<typeof fetch>(async () => responseJson({ value: 1 }))
    });
    await expect(json.requestJson<{ value: number }>('/json')).resolves.toEqual(
      { value: 1 }
    );

    const text = new ApiClient({
      fetch: vi.fn<typeof fetch>(async () => new Response('a,b\n1,2'))
    });
    await expect(text.requestText('/records/export.csv')).resolves.toBe(
      'a,b\n1,2'
    );

    const blob = new Blob(['binary'], { type: 'application/octet-stream' });
    const binary = new ApiClient({
      fetch: vi.fn<typeof fetch>(async () => new Response(blob))
    });
    await expect(binary.requestBlob('/download')).resolves.toEqual(blob);
  });

  it('JSON detailが文字列のときだけ表示可能なエラーに含める', async () => {
    const client = new ApiClient({
      fetch: vi.fn<typeof fetch>(async () =>
        responseJson(
          { detail: '入力内容を確認してください。' },
          { status: 400 }
        )
      )
    });
    await expect(client.requestJson('/records')).rejects.toMatchObject({
      kind: 'http',
      status: 400,
      message: '入力内容を確認してください。'
    } satisfies Partial<ApiHttpError>);

    const unknownDetail = new ApiClient({
      fetch: vi.fn<typeof fetch>(async () =>
        responseJson({ detail: { secret: 'do-not-show' } }, { status: 400 })
      )
    });
    await expect(unknownDetail.requestJson('/records')).rejects.toMatchObject({
      message: GENERIC_API_ERROR_MESSAGE
    });

    const html = new ApiClient({
      fetch: vi.fn<typeof fetch>(
        async () =>
          new Response('<h1>proxy details</h1>', {
            status: 502,
            headers: { 'content-type': 'text/html' }
          })
      )
    });
    await expect(html.requestJson('/records')).rejects.toMatchObject({
      message: GENERIC_API_ERROR_MESSAGE
    });
  });

  it('利用者cancelと15秒timeoutを異なるエラーにする', async () => {
    vi.useFakeTimers();
    try {
      const cancelled = new ApiClient({ fetch: abortableFetch() });
      const controller = new AbortController();
      const request = cancelled.requestJson('/records', {
        signal: controller.signal
      });
      controller.abort();
      await expect(request).rejects.toBeInstanceOf(ApiRequestCancelledError);

      const timedOut = new ApiClient({ fetch: abortableFetch() });
      const timeoutRequest = timedOut.requestJson('/records');
      const timeoutExpectation =
        expect(timeoutRequest).rejects.toBeInstanceOf(ApiTimeoutError);
      await vi.advanceTimersByTimeAsync(15_000);
      await timeoutExpectation;
    } finally {
      vi.useRealTimers();
    }
  });

  it('readinessの503は本文を正常な状態情報として読む', async () => {
    const client = new ApiClient({
      fetch: vi.fn<typeof fetch>(async () =>
        responseJson(
          {
            status: 'not_ready',
            database_ready: false,
            database_migration_current: false,
            cloud_audio_enabled: false,
            cloud_audio_job_storage_ready: null,
            cloud_audio_llm_configured: null,
            line_delivery_configured: false
          },
          { status: 503 }
        )
      )
    });

    await expect(getRuntimeReadiness(client)).resolves.toMatchObject({
      status: 'not_ready'
    });
  });

  it('成功応答が壊れたJSONなら安全なinvalid-responseにする', async () => {
    const client = new ApiClient({
      fetch: vi.fn<typeof fetch>(
        async () =>
          new Response('<html>', { headers: { 'content-type': 'text/html' } })
      )
    });
    await expect(client.requestJson('/records')).rejects.toBeInstanceOf(
      ApiInvalidResponseError
    );
  });
});
