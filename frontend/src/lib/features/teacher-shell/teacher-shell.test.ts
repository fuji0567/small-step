import { describe, expect, it, vi } from 'vitest';

import { createTeacherSession } from '$lib/auth';
import { TeacherShellState } from './teacher-shell.svelte';

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' }
  });
}

function school(id = 'school-1') {
  return {
    id,
    name: 'ひまわり園',
    timezone: 'Asia/Tokyo',
    digest_time: '17:00',
    created_at: '2026-09-11T00:00:00Z'
  };
}

describe('TeacherShellState', () => {
  it('developmentではログインなしで管理者用シェルを開く', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ auth_mode: 'development' }))
      .mockResolvedValueOnce(jsonResponse([school()]));
    const shell = new TeacherShellState(fetchMock);

    await shell.initialize(null);

    expect(shell.phase).toBe('ready');
    expect(shell.isSchoolAdmin).toBe(true);
    expect(shell.schools.schoolId).toBe('school-1');
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/v1/auth/config',
      expect.any(Object)
    );
  });

  it('保存済みtokenで教員情報と所属園を取得する', async () => {
    const storage = {
      getItem: vi.fn(() => 'saved-jwt'),
      setItem: vi.fn(),
      removeItem: vi.fn()
    };
    const teacher = {
      id: 'teacher-1',
      school_id: 'school-1',
      name: '山田先生',
      email: 'teacher@example.com',
      role: 'teacher',
      is_auth_linked: true,
      is_active: true,
      disabled_at: null,
      created_at: '2026-09-11T00:00:00Z'
    };
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        jsonResponse({
          auth_mode: 'supabase',
          supabase_url: 'https://example.supabase.co',
          supabase_publishable_key: 'public-key'
        })
      )
      .mockResolvedValueOnce(jsonResponse(teacher))
      .mockResolvedValueOnce(jsonResponse([school()]));
    const shell = new TeacherShellState(fetchMock);

    await shell.initialize(createTeacherSession(storage));

    expect(shell.phase).toBe('ready');
    expect(shell.teacher?.name).toBe('山田先生');
    expect(shell.isSchoolAdmin).toBe(false);
    const meRequest = fetchMock.mock.calls[1]?.[1];
    expect(new Headers(meRequest?.headers).get('Authorization')).toBe(
      'Bearer saved-jwt'
    );
  });

  it('パスワード認証成功後にtokenを保存してアプリを開く', async () => {
    const storage = {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
      removeItem: vi.fn()
    };
    const teacher = {
      id: 'teacher-1',
      school_id: 'school-1',
      name: '山田先生',
      email: 'teacher@example.com',
      role: 'teacher',
      is_auth_linked: true,
      is_active: true,
      disabled_at: null,
      created_at: '2026-09-11T00:00:00Z'
    };
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        jsonResponse({
          auth_mode: 'supabase',
          supabase_url: 'https://example.supabase.co',
          supabase_publishable_key: 'public-key'
        })
      )
      .mockResolvedValueOnce(jsonResponse({ access_token: 'new-jwt' }))
      .mockResolvedValueOnce(jsonResponse(teacher))
      .mockResolvedValueOnce(jsonResponse([school()]));
    const shell = new TeacherShellState(fetchMock);
    const session = createTeacherSession(storage);
    await shell.initialize(session);

    await shell.signIn('teacher@example.com', 'password');

    expect(shell.phase).toBe('ready');
    expect(storage.setItem).toHaveBeenCalledWith(
      'small-step.access-token',
      'new-jwt'
    );
  });

  it('401になった保存済みtokenを破棄して再ログインを求める', async () => {
    const storage = {
      getItem: vi.fn(() => 'expired-jwt'),
      setItem: vi.fn(),
      removeItem: vi.fn()
    };
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        jsonResponse({
          auth_mode: 'supabase',
          supabase_url: 'https://example.supabase.co',
          supabase_publishable_key: 'public-key'
        })
      )
      .mockResolvedValueOnce(jsonResponse({ detail: 'expired' }, 401));
    const shell = new TeacherShellState(fetchMock);

    await shell.initialize(createTeacherSession(storage));

    expect(shell.phase).toBe('login');
    expect(shell.errorMessage).toContain('ログインし直してください');
    expect(storage.removeItem).toHaveBeenCalledWith('small-step.access-token');
  });

  it('403の未紐付け教員を既存の先生へ紐付ける', async () => {
    const storage = {
      getItem: vi.fn(() => 'saved-jwt'),
      setItem: vi.fn(),
      removeItem: vi.fn()
    };
    const teacher = {
      id: 'teacher-1',
      school_id: 'school-1',
      name: '山田先生',
      email: 'teacher@example.com',
      role: 'teacher',
      is_auth_linked: true,
      is_active: true,
      disabled_at: null,
      created_at: '2026-09-11T00:00:00Z'
    };
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        jsonResponse({
          auth_mode: 'supabase',
          supabase_url: 'https://example.supabase.co',
          supabase_publishable_key: 'public-key'
        })
      )
      .mockResolvedValueOnce(jsonResponse({ detail: 'not linked' }, 403))
      .mockResolvedValueOnce(jsonResponse(teacher))
      .mockResolvedValueOnce(jsonResponse([school()]));
    const shell = new TeacherShellState(fetchMock);

    await shell.initialize(createTeacherSession(storage));

    expect(shell.phase).toBe('ready');
    expect(shell.teacher?.id).toBe('teacher-1');
    expect(fetchMock.mock.calls[2]?.[0]).toBe('/api/v1/auth/link-teacher');
  });

  it('未登録の初回管理者には園選択を表示する', async () => {
    const storage = {
      getItem: vi.fn(() => 'saved-jwt'),
      setItem: vi.fn(),
      removeItem: vi.fn()
    };
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        jsonResponse({
          auth_mode: 'supabase',
          supabase_url: 'https://example.supabase.co',
          supabase_publishable_key: 'public-key'
        })
      )
      .mockResolvedValueOnce(jsonResponse({ detail: 'not linked' }, 403))
      .mockResolvedValueOnce(jsonResponse({ detail: 'not registered' }, 404))
      .mockResolvedValueOnce(jsonResponse([school()]));
    const shell = new TeacherShellState(fetchMock);

    await shell.initialize(createTeacherSession(storage));

    expect(shell.phase).toBe('bootstrap');
    expect(shell.bootstrapSchools).toHaveLength(1);
    expect(storage.removeItem).not.toHaveBeenCalled();
  });

  it('初回管理者登録を完了して所属園を開く', async () => {
    const storage = {
      getItem: vi.fn(() => 'saved-jwt'),
      setItem: vi.fn(),
      removeItem: vi.fn()
    };
    const bootstrapTeacher = {
      id: 'admin-1',
      school_id: 'school-1',
      name: '管理者先生',
      email: 'admin@example.com',
      role: 'school_admin',
      is_auth_linked: true,
      is_active: true,
      disabled_at: null,
      created_at: '2026-09-11T00:00:00Z'
    };
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        jsonResponse({
          auth_mode: 'supabase',
          supabase_url: 'https://example.supabase.co',
          supabase_publishable_key: 'public-key'
        })
      )
      .mockResolvedValueOnce(jsonResponse({ detail: 'not linked' }, 403))
      .mockResolvedValueOnce(jsonResponse({ detail: 'not registered' }, 404))
      .mockResolvedValueOnce(jsonResponse([school()]))
      .mockResolvedValueOnce(jsonResponse(bootstrapTeacher))
      .mockResolvedValueOnce(jsonResponse([school()]));
    const shell = new TeacherShellState(fetchMock);
    await shell.initialize(createTeacherSession(storage));

    await shell.completeBootstrap('school-1', '管理者先生');

    expect(shell.phase).toBe('ready');
    expect(shell.isSchoolAdmin).toBe(true);
    expect(fetchMock.mock.calls[4]?.[0]).toBe('/api/v1/auth/bootstrap/teacher');
  });

  it('園切替時に登録された画面固有状態をリセットする', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ auth_mode: 'development' }))
      .mockResolvedValueOnce(jsonResponse([school(), school('school-2')]));
    const shell = new TeacherShellState(fetchMock);
    await shell.initialize(null);
    const reset = vi.fn();
    shell.schools.onSchoolChangeReset(reset);

    shell.selectSchool('school-2');

    expect(reset).toHaveBeenCalledWith('school-2');
  });

  it('共有controller経由で後続機能の再取得を実行する', async () => {
    const shell = new TeacherShellState(vi.fn<typeof fetch>());
    const refreshRecords = vi.fn();
    shell.controller.register('records', refreshRecords);

    await shell.refresh(['records']);

    expect(refreshRecords).toHaveBeenCalledOnce();
  });

  it('対象scopeのrefresh完了後にナビ件数も再取得する', async () => {
    const counts = {
      pending_review_records: 2,
      notification_attention: 3,
      failed_audio_jobs: 4,
      invitations_not_issued: 5,
      readiness_issues: 1
    };
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(jsonResponse({ auth_mode: 'development' }))
      .mockResolvedValueOnce(jsonResponse([school()]))
      .mockResolvedValueOnce(jsonResponse(counts));
    const shell = new TeacherShellState(fetchMock);
    const refreshRecords = vi.fn();
    shell.controller.register('records', refreshRecords);

    await shell.initialize(null);
    await shell.controller.refresh(['records']);

    expect(refreshRecords).toHaveBeenCalledOnce();
    expect(fetchMock.mock.calls[2]?.[0]).toBe(
      '/api/v1/navigation-badges?school_id=school-1'
    );
    expect(shell.navigationBadges.counts).toEqual(counts);
  });

  it('ログアウト時にtokenと園・教員の状態を消去する', async () => {
    const storage = {
      getItem: vi.fn(() => 'saved-jwt'),
      setItem: vi.fn(),
      removeItem: vi.fn()
    };
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        jsonResponse({
          auth_mode: 'supabase',
          supabase_url: 'https://example.supabase.co',
          supabase_publishable_key: 'public-key'
        })
      )
      .mockResolvedValueOnce(
        jsonResponse({
          id: 'teacher-1',
          school_id: 'school-1',
          name: '山田先生',
          email: null,
          role: 'school_admin',
          is_auth_linked: true,
          is_active: true,
          disabled_at: null,
          created_at: '2026-09-11T00:00:00Z'
        })
      )
      .mockResolvedValueOnce(jsonResponse([school()]));
    const shell = new TeacherShellState(fetchMock);
    await shell.initialize(createTeacherSession(storage));

    shell.logout();

    expect(storage.removeItem).toHaveBeenCalledWith('small-step.access-token');
    expect(shell.phase).toBe('login');
    expect(shell.teacher).toBeNull();
    expect(shell.schools.schools).toEqual([]);
  });
});
