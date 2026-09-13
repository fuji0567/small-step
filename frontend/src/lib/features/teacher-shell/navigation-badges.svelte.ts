import type { ApiClient } from '$lib/api';

import {
  EMPTY_NAVIGATION_BADGES,
  NavigationBadgeService,
  type NavigationBadgeCounts
} from './navigation-badges';

function emptyCounts(): NavigationBadgeCounts {
  return { ...EMPTY_NAVIGATION_BADGES };
}

/** Reactive, failure-isolated state for the teacher shell navigation. */
export class NavigationBadgeState {
  readonly #service: NavigationBadgeService;
  #counts = $state<NavigationBadgeCounts>(emptyCounts());
  #requestVersion = 0;
  #activeRequest: AbortController | null = null;
  #activeSchoolId: string | null = null;
  #activePromise: Promise<void> | null = null;

  constructor(api: ApiClient) {
    this.#service = new NavigationBadgeService(api);
  }

  get counts(): NavigationBadgeCounts {
    return this.#counts;
  }

  reset(): void {
    this.#requestVersion += 1;
    this.#activeRequest?.abort();
    this.#activeRequest = null;
    this.#activeSchoolId = null;
    this.#activePromise = null;
    this.#counts = emptyCounts();
  }

  load(schoolId: string | null, signal?: AbortSignal): Promise<void> {
    if (!schoolId) {
      this.reset();
      return Promise.resolve();
    }

    // The layout effect and afterNavigate can observe the same ready state in
    // one navigation. Share that request instead of hitting the endpoint twice.
    if (
      this.#activePromise &&
      this.#activeSchoolId === schoolId &&
      !signal?.aborted
    ) {
      return this.#activePromise;
    }

    this.#activeRequest?.abort();
    this.#activeRequest = null;
    this.#activeSchoolId = schoolId;
    const request = new AbortController();
    this.#activeRequest = request;
    const cancelFromCaller = () => {
      if (!request.signal.aborted) request.abort(signal?.reason);
    };
    if (signal?.aborted) cancelFromCaller();
    else signal?.addEventListener('abort', cancelFromCaller, { once: true });

    const version = ++this.#requestVersion;
    const pending = this.#performLoad(
      schoolId,
      request,
      signal,
      cancelFromCaller,
      version
    );
    this.#activePromise = pending;
    void pending.finally(() => {
      if (this.#activePromise === pending) {
        this.#activePromise = null;
        this.#activeSchoolId = null;
      }
    });
    return pending;
  }

  refresh(schoolId: string | null): Promise<void> {
    if (!schoolId) {
      this.reset();
      return Promise.resolve();
    }
    this.#activeRequest?.abort();
    this.#activeRequest = null;
    this.#activePromise = null;
    return this.load(schoolId);
  }

  async #performLoad(
    schoolId: string,
    request: AbortController,
    signal: AbortSignal | undefined,
    cancelFromCaller: () => void,
    version: number
  ): Promise<void> {
    try {
      const counts = await this.#service.load(schoolId, request.signal);
      if (request.signal.aborted || version !== this.#requestVersion) return;
      this.#counts = counts;
    } catch {
      // A badge summary is supplemental UI. Keep the shell usable when the
      // endpoint is unavailable or returns an invalid response.
      if (request.signal.aborted || version !== this.#requestVersion) return;
      this.#counts = emptyCounts();
    } finally {
      signal?.removeEventListener('abort', cancelFromCaller);
      if (this.#activeRequest === request) this.#activeRequest = null;
    }
  }
}
