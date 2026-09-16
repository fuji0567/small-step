import type { LocalRecordingSession } from "./types";

const DATABASE_NAME = "small-step-recorder";
const STORE_NAME = "sessions";
const DATABASE_VERSION = 1;
export const MAX_LOCAL_SESSIONS = 3;
export const SESSION_TTL_MS = 24 * 60 * 60 * 1000;

export interface SessionRepository {
  list(): Promise<LocalRecordingSession[]>;
  put(session: LocalRecordingSession): Promise<void>;
  delete(clientSessionId: string): Promise<void>;
  cleanup(now?: number): Promise<string[]>;
}

function requestResult<T>(request: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () =>
      reject(request.error ?? new Error("IndexedDB error"));
  });
}

function transactionDone(transaction: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    transaction.oncomplete = () => resolve();
    transaction.onerror = () =>
      reject(transaction.error ?? new Error("IndexedDB error"));
    transaction.onabort = () =>
      reject(transaction.error ?? new Error("IndexedDB aborted"));
  });
}

export class IndexedDbSessionRepository implements SessionRepository {
  readonly #indexedDb: IDBFactory;
  #database: Promise<IDBDatabase> | null = null;

  constructor(indexedDb: IDBFactory = globalThis.indexedDB) {
    this.#indexedDb = indexedDb;
  }

  list(): Promise<LocalRecordingSession[]> {
    return this.#withStore("readonly", (store) =>
      requestResult(store.getAll()),
    );
  }

  async put(session: LocalRecordingSession): Promise<void> {
    const sessions = await this.list();
    const isNew = !sessions.some(
      (item) => item.clientSessionId === session.clientSessionId,
    );
    if (isNew && sessions.length >= MAX_LOCAL_SESSIONS) {
      throw new Error(
        "未送信の録音が3件あります。送信または破棄してください。",
      );
    }
    await this.#withStore("readwrite", async (store) => {
      await requestResult(store.put(session));
    });
  }

  async delete(clientSessionId: string): Promise<void> {
    await this.#withStore("readwrite", async (store) => {
      await requestResult(store.delete(clientSessionId));
    });
  }

  async cleanup(now = Date.now()): Promise<string[]> {
    const expired = (await this.list()).filter(
      (session) => now - session.updatedAt >= SESSION_TTL_MS,
    );
    for (const session of expired) await this.delete(session.clientSessionId);
    return expired.map((session) => session.clientSessionId);
  }

  async #open(): Promise<IDBDatabase> {
    if (this.#database) return this.#database;
    this.#database = new Promise((resolve, reject) => {
      const request = this.#indexedDb.open(DATABASE_NAME, DATABASE_VERSION);
      request.onupgradeneeded = () => {
        if (!request.result.objectStoreNames.contains(STORE_NAME)) {
          request.result.createObjectStore(STORE_NAME, {
            keyPath: "clientSessionId",
          });
        }
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () =>
        reject(request.error ?? new Error("IndexedDB error"));
    });
    return this.#database;
  }

  async #withStore<T>(
    mode: IDBTransactionMode,
    operation: (store: IDBObjectStore) => Promise<T>,
  ): Promise<T> {
    const database = await this.#open();
    const transaction = database.transaction(STORE_NAME, mode);
    const value = await operation(transaction.objectStore(STORE_NAME));
    await transactionDone(transaction);
    return value;
  }
}
