export type ApiErrorKind =
  'http' | 'timeout' | 'cancelled' | 'network' | 'invalid-response';

export const GENERIC_API_ERROR_MESSAGE = '通信に失敗しました。';
export const API_TIMEOUT_MESSAGE =
  '通信が時間内に完了しませんでした。FastAPIのターミナルを確認して再試行してください。';
export const API_CANCELLED_MESSAGE = '操作をキャンセルしました。';

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status: number | null;

  constructor(
    message: string,
    kind: ApiErrorKind,
    options: { status?: number; cause?: unknown } = {}
  ) {
    super(
      message,
      options.cause === undefined ? undefined : { cause: options.cause }
    );
    this.name = 'ApiError';
    this.kind = kind;
    this.status = options.status ?? null;
  }
}

export class ApiHttpError extends ApiError {
  constructor(message: string, status: number) {
    super(message, 'http', { status });
    this.name = 'ApiHttpError';
  }
}

export class ApiTimeoutError extends ApiError {
  constructor(cause?: unknown) {
    super(API_TIMEOUT_MESSAGE, 'timeout', { cause });
    this.name = 'ApiTimeoutError';
  }
}

export class ApiRequestCancelledError extends ApiError {
  constructor(cause?: unknown) {
    super(API_CANCELLED_MESSAGE, 'cancelled', { cause });
    this.name = 'ApiRequestCancelledError';
  }
}

export class ApiNetworkError extends ApiError {
  constructor(cause?: unknown) {
    super(GENERIC_API_ERROR_MESSAGE, 'network', { cause });
    this.name = 'ApiNetworkError';
  }
}

export class ApiInvalidResponseError extends ApiError {
  constructor(cause?: unknown) {
    super(GENERIC_API_ERROR_MESSAGE, 'invalid-response', { cause });
    this.name = 'ApiInvalidResponseError';
  }
}
