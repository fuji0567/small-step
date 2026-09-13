export const TEACHER_ACCESS_TOKEN_KEY = 'small-step.access-token';
export const GUARDIAN_ARCHIVE_TOKEN_KEY = 'small-step.guardian-archive-token';

export interface SessionStorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem(key: string): void;
}

export interface BrowserSessionEnvironment {
  readonly storage: SessionStorageLike;
  readonly hash: string;
  readonly pathname: string;
  replaceUrl(pathname: string): void;
}

export interface SessionTokenStore {
  readonly key: string;
  read(): string | null;
  write(token: string): void;
  clear(): void;
}

export function createSessionTokenStore(
  storage: SessionStorageLike,
  key: string
): SessionTokenStore {
  return {
    key,
    read: () => storage.getItem(key),
    write: (token: string) => storage.setItem(key, token),
    clear: () => storage.removeItem(key)
  };
}

export function createTeacherSession(
  storage: SessionStorageLike
): SessionTokenStore {
  return createSessionTokenStore(storage, TEACHER_ACCESS_TOKEN_KEY);
}

export function createGuardianSession(
  storage: SessionStorageLike
): SessionTokenStore {
  return createSessionTokenStore(storage, GUARDIAN_ARCHIVE_TOKEN_KEY);
}

export function browserSessionEnvironment(): BrowserSessionEnvironment | null {
  if (typeof window === 'undefined') return null;

  try {
    const storage = window.sessionStorage;
    return {
      storage,
      hash: window.location.hash,
      pathname: window.location.pathname,
      replaceUrl: (pathname: string) =>
        window.history.replaceState(null, '', pathname)
    };
  } catch {
    // Storage may be unavailable under browser privacy policies.
    return null;
  }
}

export function initializeTeacherSession(
  environment: BrowserSessionEnvironment | null = browserSessionEnvironment()
): SessionTokenStore | null {
  return environment === null
    ? null
    : createTeacherSession(environment.storage);
}

export function initializeGuardianSession(
  environment: BrowserSessionEnvironment | null = browserSessionEnvironment()
): SessionTokenStore | null {
  if (environment === null) return null;

  const session = createGuardianSession(environment.storage);
  const tokenFromUrl = environment.hash.slice(1);
  if (tokenFromUrl.startsWith('ssa_')) {
    session.write(tokenFromUrl);
    environment.replaceUrl(environment.pathname);
  }
  return session;
}
