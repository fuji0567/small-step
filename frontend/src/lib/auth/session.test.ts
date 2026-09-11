import { afterEach, describe, expect, it, vi } from 'vitest';

afterEach(() => {
  vi.unstubAllGlobals();
  vi.resetModules();
});

function memoryStorage() {
  const values = new Map<string, string>();
  return {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => values.set(key, value),
    removeItem: (key: string) => values.delete(key)
  };
}

describe('session helpers', () => {
  it('import時にはwindowやstorageへ触れない', async () => {
    const sessionStorage = vi.fn(() => {
      throw new Error('must not be accessed during import');
    });
    vi.stubGlobal('window', {
      get sessionStorage() {
        return sessionStorage();
      }
    });

    await expect(import('./session')).resolves.toBeDefined();
    expect(sessionStorage).not.toHaveBeenCalled();
  });

  it('先生tokenを専用sessionStorage keyで読み書き・削除する', async () => {
    const { createTeacherSession, TEACHER_ACCESS_TOKEN_KEY } =
      await import('./session');
    const storage = memoryStorage();
    const session = createTeacherSession(storage);

    expect(session.key).toBe('small-step.access-token');
    session.write('teacher-token');
    expect(storage.getItem(TEACHER_ACCESS_TOKEN_KEY)).toBe('teacher-token');
    expect(session.read()).toBe('teacher-token');
    session.clear();
    expect(session.read()).toBeNull();
  });

  it('保護者tokenをhashから一度だけ保存し、URLから秘密を除く', async () => {
    const { initializeGuardianSession, GUARDIAN_ARCHIVE_TOKEN_KEY } =
      await import('./session');
    const storage = memoryStorage();
    const replaceUrl = vi.fn();

    const session = initializeGuardianSession({
      storage,
      hash: '#ssa_archive-secret',
      pathname: '/guardian/',
      replaceUrl
    });

    expect(session?.read()).toBe('ssa_archive-secret');
    expect(storage.getItem(GUARDIAN_ARCHIVE_TOKEN_KEY)).toBe(
      'ssa_archive-secret'
    );
    expect(replaceUrl).toHaveBeenCalledWith('/guardian/');
  });

  it('不正なhashを保存せず、既存の保護者sessionを復元する', async () => {
    const { createGuardianSession, initializeGuardianSession } =
      await import('./session');
    const storage = memoryStorage();
    createGuardianSession(storage).write('ssa_saved');
    const replaceUrl = vi.fn();

    const session = initializeGuardianSession({
      storage,
      hash: '#not-an-archive-token',
      pathname: '/guardian/',
      replaceUrl
    });

    expect(session?.read()).toBe('ssa_saved');
    expect(replaceUrl).not.toHaveBeenCalled();
  });
});
