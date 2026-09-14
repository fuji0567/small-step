import { ApiClient, ApiHttpError } from '$lib/api';
import type { SessionTokenStore } from '$lib/auth';
import {
  AppController,
  SchoolContext,
  type InvalidationScope,
  type SchoolSummary
} from '$lib/state';

import { signInWithSupabasePassword } from './auth';
import { NavigationBadgeState } from './navigation-badges.svelte';
import type {
  AuthClientConfig,
  TeacherProfile,
  TeacherShellPhase,
  TeacherShellSnapshot
} from './types';

const NAVIGATION_BADGE_REFRESH_SCOPES = new Set<InvalidationScope>([
  'records',
  'notifications',
  'audioJobs',
  'children',
  'invitations',
  'runtimeReadiness'
]);

class TeacherShellController extends AppController {
  readonly #refreshNavigationBadges: () => Promise<void>;

  constructor(refreshNavigationBadges: () => Promise<void>) {
    super();
    this.#refreshNavigationBadges = refreshNavigationBadges;
  }

  override async refresh(scopes: Iterable<InvalidationScope>): Promise<void> {
    const requestedScopes = [...scopes];
    await super.refresh(requestedScopes);
    if (
      requestedScopes.some((scope) =>
        NAVIGATION_BADGE_REFRESH_SCOPES.has(scope)
      )
    ) {
      await this.#refreshNavigationBadges();
    }
  }
}

export class TeacherShellState {
  readonly schools = new SchoolContext();
  readonly navigationBadges: NavigationBadgeState;
  readonly controller: AppController;
  #phase = $state<TeacherShellPhase>('initializing');
  #config = $state<AuthClientConfig | null>(null);
  #teacher = $state<TeacherProfile | null>(null);
  #accessToken = $state<string | null>(null);
  #errorMessage = $state<string | null>(null);
  #bootstrapSchools = $state.raw<readonly SchoolSummary[]>([]);
  #session: SessionTokenStore | null = null;
  readonly #fetch: typeof fetch;
  readonly api: ApiClient;

  constructor(fetchFn: typeof fetch) {
    this.#fetch = fetchFn;
    this.api = new ApiClient({
      accessToken: () => this.#accessToken,
      fetch: fetchFn
    });
    this.navigationBadges = new NavigationBadgeState(this.api);
    this.controller = new TeacherShellController(() =>
      this.#refreshNavigationBadges()
    );
    this.schools.onSchoolChangeReset(() => this.navigationBadges.reset());
  }

  get phase(): TeacherShellPhase {
    return this.#phase;
  }

  get teacher(): TeacherProfile | null {
    return this.#teacher;
  }

  get errorMessage(): string | null {
    return this.#errorMessage;
  }

  get bootstrapSchools(): readonly SchoolSummary[] {
    return this.#bootstrapSchools;
  }

  get isSchoolAdmin(): boolean {
    return (
      this.#config?.auth_mode === 'development' ||
      this.#teacher?.role === 'school_admin'
    );
  }

  get canLogout(): boolean {
    return this.#config?.auth_mode === 'supabase';
  }

  get voiceprintEnabled(): boolean {
    return this.#config?.voiceprint_enabled === true;
  }

  get snapshot(): TeacherShellSnapshot {
    return {
      phase: this.#phase,
      teacher: this.#teacher,
      schools: this.schools.schools,
      schoolId: this.schools.schoolId,
      isSchoolAdmin: this.isSchoolAdmin
    };
  }

  async initialize(session: SessionTokenStore | null): Promise<void> {
    this.#session = session;
    this.#phase = 'initializing';
    this.#errorMessage = null;
    try {
      this.#config = await this.#requireJson<AuthClientConfig>('auth/config');
      if (this.#config.auth_mode === 'development') {
        await this.#openApp(null);
        return;
      }

      this.#accessToken = session?.read() ?? null;
      if (!this.#accessToken) {
        this.#phase = 'login';
        return;
      }

      try {
        await this.#establishTeacherSession();
      } catch {
        this.#clearAuthentication();
        this.#errorMessage =
          'セッションの有効期限が切れました。ログインし直してください。';
        this.#phase = 'login';
      }
    } catch (error) {
      this.#errorMessage = this.#messageFrom(error);
      this.#phase = 'fatal';
    }
  }

  async signIn(email: string, password: string): Promise<void> {
    if (
      this.#config?.auth_mode !== 'supabase' ||
      !this.#config.supabase_url ||
      !this.#config.supabase_publishable_key
    ) {
      this.#errorMessage = 'Supabaseの公開設定が不足しています。';
      return;
    }

    this.#phase = 'initializing';
    this.#errorMessage = null;
    try {
      const token = await signInWithSupabasePassword({
        email,
        password,
        supabaseUrl: this.#config.supabase_url,
        publishableKey: this.#config.supabase_publishable_key,
        fetch: this.#fetch
      });
      this.#accessToken = token;
      this.#session?.write(token);
      await this.#establishTeacherSession();
    } catch (error) {
      this.#clearAuthentication();
      this.#errorMessage = this.#messageFrom(error);
      this.#phase = 'login';
    }
  }

  async completeBootstrap(schoolId: string, name: string): Promise<void> {
    this.#phase = 'initializing';
    this.#errorMessage = null;
    try {
      const teacher = await this.#requireJson<TeacherProfile>(
        'auth/bootstrap/teacher',
        { method: 'POST', json: { school_id: schoolId, name } }
      );
      await this.#openApp(teacher);
    } catch (error) {
      this.#errorMessage = this.#messageFrom(error);
      this.#phase = 'bootstrap';
    }
  }

  async reloadSchools(): Promise<void> {
    await this.#loadSchools();
  }

  selectSchool(schoolId: string): void {
    this.schools.selectSchool(schoolId);
  }

  refresh(scopes: Iterable<InvalidationScope>): Promise<void> {
    return this.controller.refresh(scopes);
  }

  logout(): void {
    this.#clearAuthentication();
    this.#config = this.#config?.auth_mode === 'supabase' ? this.#config : null;
    this.#errorMessage = 'ログアウトしました。';
    this.#phase = this.#config ? 'login' : 'initializing';
  }

  async #establishTeacherSession(): Promise<void> {
    let teacher: TeacherProfile;
    try {
      teacher = await this.#requireJson<TeacherProfile>('auth/me');
    } catch (error) {
      if (!(error instanceof ApiHttpError) || error.status !== 403) throw error;
      try {
        teacher = await this.#requireJson<TeacherProfile>('auth/link-teacher', {
          method: 'POST'
        });
      } catch (linkError) {
        if (!(linkError instanceof ApiHttpError) || linkError.status !== 404) {
          throw linkError;
        }
        this.#bootstrapSchools = await this.#requireJson<SchoolSummary[]>(
          'auth/bootstrap/schools'
        );
        if (this.#bootstrapSchools.length === 0) {
          throw new Error(
            '紐付ける園がありません。先に園を登録してください。',
            { cause: linkError }
          );
        }
        this.#phase = 'bootstrap';
        return;
      }
    }
    await this.#openApp(teacher);
  }

  async #openApp(teacher: TeacherProfile | null): Promise<void> {
    this.#teacher = teacher;
    this.#bootstrapSchools = [];
    await this.#loadSchools();
    this.#phase = 'ready';
  }

  async #loadSchools(): Promise<void> {
    const schools = await this.#requireJson<SchoolSummary[]>('schools');
    this.schools.setSchools(schools);
    const preferredSchoolId =
      this.#teacher?.school_id ?? schools[0]?.id ?? null;
    this.schools.selectSchool(preferredSchoolId);
  }

  #clearAuthentication(): void {
    this.#session?.clear();
    this.#accessToken = null;
    this.#teacher = null;
    this.#bootstrapSchools = [];
    this.schools.setSchools([]);
    this.schools.selectSchool(null);
  }

  async #refreshNavigationBadges(): Promise<void> {
    if (this.#phase !== 'ready' || !this.schools.schoolId) return;
    await this.navigationBadges.refresh(this.schools.schoolId);
  }

  async #requireJson<T>(
    path: string,
    options: Parameters<ApiClient['requestJson']>[1] = {}
  ): Promise<T> {
    const value = await this.api.requestJson<T>(path, options);
    if (value === null)
      throw new Error('APIから必要なデータが返されませんでした。');
    return value;
  }

  #messageFrom(error: unknown): string {
    return error instanceof Error ? error.message : '通信に失敗しました。';
  }
}
