import {
  ApiHttpError,
  ApiInvalidResponseError,
  ApiNetworkError,
  ApiRequestCancelledError,
  ApiTimeoutError,
  GENERIC_API_ERROR_MESSAGE
} from './errors';

export const API_BASE_PATH = '/api/v1';
export const DEFAULT_API_TIMEOUT_MS = 15_000;

export type AccessTokenProvider = () => string | null;

export interface ApiClientOptions {
  accessToken?: AccessTokenProvider;
  fetch?: typeof fetch;
  timeoutMs?: number;
}

export interface ApiRequestOptions extends Omit<
  RequestInit,
  'body' | 'headers' | 'signal'
> {
  acceptedStatuses?: readonly number[];
  body?: BodyInit | null;
  headers?: HeadersInit;
  json?: unknown;
  signal?: AbortSignal;
  timeoutMs?: number;
}

type ResponseKind = 'json' | 'blob' | 'text';

function apiPath(path: string): string {
  if (/^[a-z][a-z\d+.-]*:/i.test(path) || path.startsWith('//')) {
    throw new TypeError('API path must be same-origin');
  }
  if (path === API_BASE_PATH || path.startsWith(`${API_BASE_PATH}/`))
    return path;
  return `${API_BASE_PATH}/${path.replace(/^\/+/, '')}`;
}

function isJsonContentType(response: Response): boolean {
  const contentType = response.headers.get('content-type')?.toLowerCase() ?? '';
  return (
    contentType.includes('application/json') || contentType.includes('+json')
  );
}

async function safeErrorMessage(response: Response): Promise<string> {
  if (!isJsonContentType(response)) return GENERIC_API_ERROR_MESSAGE;
  try {
    const payload: unknown = await response.json();
    if (
      typeof payload === 'object' &&
      payload !== null &&
      'detail' in payload &&
      typeof payload.detail === 'string'
    ) {
      return payload.detail;
    }
  } catch {
    // Unexpected and non-JSON response bodies must not be shown to users.
  }
  return GENERIC_API_ERROR_MESSAGE;
}

export class ApiClient {
  readonly #accessToken: AccessTokenProvider;
  readonly #fetch: typeof fetch;
  readonly #timeoutMs: number;

  constructor(options: ApiClientOptions = {}) {
    this.#accessToken = options.accessToken ?? (() => null);
    this.#fetch =
      options.fetch ?? ((input, init) => globalThis.fetch(input, init));
    this.#timeoutMs = options.timeoutMs ?? DEFAULT_API_TIMEOUT_MS;
  }

  requestJson<T>(
    path: string,
    options: ApiRequestOptions = {}
  ): Promise<T | null> {
    return this.#request<T>(path, 'json', options);
  }

  requestBlob(
    path: string,
    options: ApiRequestOptions = {}
  ): Promise<Blob | null> {
    return this.#request<Blob>(path, 'blob', options);
  }

  requestText(
    path: string,
    options: ApiRequestOptions = {}
  ): Promise<string | null> {
    return this.#request<string>(path, 'text', options);
  }

  async #request<T>(
    path: string,
    responseKind: ResponseKind,
    options: ApiRequestOptions
  ): Promise<T | null> {
    const requestPath = apiPath(path);
    const {
      acceptedStatuses = [],
      body,
      headers: initialHeaders,
      json,
      signal: callerSignal,
      timeoutMs = this.#timeoutMs,
      ...requestInit
    } = options;
    if (json !== undefined && body !== undefined) {
      throw new TypeError('Use either json or body, not both');
    }

    const headers = new Headers(initialHeaders);
    headers.delete('Authorization');
    const token = this.#accessToken();
    if (token) headers.set('Authorization', `Bearer ${token}`);
    if (responseKind === 'json' && !headers.has('Accept'))
      headers.set('Accept', 'application/json');
    if (json !== undefined && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json');
    }

    const controller = new AbortController();
    let abortSource: 'caller' | 'timeout' | null = null;
    const cancelFromCaller = () => {
      if (controller.signal.aborted) return;
      abortSource = 'caller';
      controller.abort(callerSignal?.reason);
    };
    if (callerSignal?.aborted) cancelFromCaller();
    else
      callerSignal?.addEventListener('abort', cancelFromCaller, { once: true });

    const timeout = globalThis.setTimeout(() => {
      if (controller.signal.aborted) return;
      abortSource = 'timeout';
      controller.abort();
    }, timeoutMs);

    let response: Response;
    try {
      response = await this.#fetch(requestPath, {
        ...requestInit,
        body: json === undefined ? body : JSON.stringify(json),
        headers,
        signal: controller.signal
      });
    } catch (error) {
      if (abortSource === 'timeout') throw new ApiTimeoutError(error);
      if (abortSource === 'caller' || callerSignal?.aborted) {
        throw new ApiRequestCancelledError(error);
      }
      throw new ApiNetworkError(error);
    } finally {
      globalThis.clearTimeout(timeout);
      callerSignal?.removeEventListener('abort', cancelFromCaller);
    }

    if (!response.ok && !acceptedStatuses.includes(response.status)) {
      throw new ApiHttpError(await safeErrorMessage(response), response.status);
    }
    if (response.status === 204) return null;

    try {
      if (responseKind === 'blob') return (await response.blob()) as T;
      if (responseKind === 'text') return (await response.text()) as T;
      return (await response.json()) as T;
    } catch (error) {
      throw new ApiInvalidResponseError(error);
    }
  }
}
