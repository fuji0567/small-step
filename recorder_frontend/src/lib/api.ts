import type { ServerRecordingSession } from "./types";

export interface RecorderApiOptions {
  fetch?: typeof fetch;
  accessToken: () => string | null;
}

export class RecorderApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "RecorderApiError";
  }
}

export class RecorderApi {
  readonly #fetch: typeof fetch;
  readonly #accessToken: () => string | null;

  constructor(options: RecorderApiOptions) {
    this.#fetch = options.fetch ?? globalThis.fetch.bind(globalThis);
    this.#accessToken = options.accessToken;
  }

  createSession(clientSessionId: string): Promise<ServerRecordingSession> {
    return this.#json("/api/v1/recorder/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ client_session_id: clientSessionId }),
    });
  }

  getSession(
    id: string,
    signal?: AbortSignal,
  ): Promise<ServerRecordingSession> {
    return this.#json(`/api/v1/recorder/sessions/${encodeURIComponent(id)}`, {
      signal,
      cache: "no-store",
    });
  }

  uploadSegment(
    id: string,
    sequence: number,
    body: FormData,
  ): Promise<ServerRecordingSession | null> {
    return this.#request(
      `/api/v1/recorder/sessions/${encodeURIComponent(id)}/segments/${sequence}`,
      { method: "PUT", body },
    );
  }

  finalize(id: string): Promise<ServerRecordingSession | null> {
    return this.#request(
      `/api/v1/recorder/sessions/${encodeURIComponent(id)}/finalize`,
      { method: "POST" },
    );
  }

  discard(id: string): Promise<void> {
    return this.#request(
      `/api/v1/recorder/sessions/${encodeURIComponent(id)}`,
      { method: "DELETE" },
    ).then(() => undefined);
  }

  async #json(
    path: string,
    init: RequestInit = {},
  ): Promise<ServerRecordingSession> {
    const result = await this.#request(path, init);
    if (result === null)
      throw new Error("サーバーから応答を受け取れませんでした。");
    return result;
  }

  async #request(
    path: string,
    init: RequestInit = {},
  ): Promise<ServerRecordingSession | null> {
    const headers = new Headers(init.headers);
    const token = this.#accessToken();
    if (!token) throw new RecorderApiError(401, "ログインが必要です。");
    headers.set("Authorization", `Bearer ${token}`);
    headers.set("Accept", "application/json");
    const response = await this.#fetch(path, { ...init, headers });
    if (!response.ok) {
      throw new RecorderApiError(
        response.status,
        response.status === 401
          ? "ログインの有効期限が切れています。再度ログインしてください。"
          : response.status === 409
            ? "録音セッションの状態が変わったため、送信を続けられません。"
            : "通信に失敗しました。",
      );
    }
    if (
      response.status === 204 ||
      response.headers.get("content-length") === "0"
    ) {
      return null;
    }
    return (await response.json()) as ServerRecordingSession;
  }
}
