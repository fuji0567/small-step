import type { InvalidationScope } from './contracts';

export type RefreshHandler = () => void | Promise<void>;

export class AppController {
  readonly #handlers = new Map<InvalidationScope, RefreshHandler>();
  readonly #inFlight = new Map<InvalidationScope, Promise<void>>();

  register(scope: InvalidationScope, handler: RefreshHandler): () => void {
    if (this.#handlers.has(scope))
      throw new Error(`Refresh handler already registered: ${scope}`);
    this.#handlers.set(scope, handler);
    return () => {
      if (this.#handlers.get(scope) === handler) this.#handlers.delete(scope);
    };
  }

  refresh(scopes: Iterable<InvalidationScope>): Promise<void> {
    const uniqueScopes = [...new Set(scopes)];
    return Promise.all(
      uniqueScopes.map((scope) => this.#refreshScope(scope))
    ).then(() => undefined);
  }

  #refreshScope(scope: InvalidationScope): Promise<void> {
    const current = this.#inFlight.get(scope);
    if (current) return current;

    const handler = this.#handlers.get(scope);
    if (!handler)
      return Promise.reject(
        new Error(`Refresh handler is not registered: ${scope}`)
      );

    const refresh = Promise.resolve().then(handler);
    this.#inFlight.set(scope, refresh);
    return refresh.finally(() => {
      if (this.#inFlight.get(scope) === refresh) this.#inFlight.delete(scope);
    });
  }
}
