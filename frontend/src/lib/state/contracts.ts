export const INVALIDATION_SCOPES = [
  'schools',
  'records',
  'recordHistory',
  'notifications',
  'children',
  'invitations',
  'audioJobs',
  'teachers',
  'edgeDevices',
  'auditEvents',
  'runtimeReadiness',
  'voiceConsent'
] as const;

export type InvalidationScope = (typeof INVALIDATION_SCOPES)[number];

export const HOME_DERIVED_SCOPES = [
  'records',
  'notifications',
  'children',
  'invitations',
  'audioJobs'
] as const satisfies readonly InvalidationScope[];

export type NavigationHistory = 'push' | 'replace';
export type NavigationFocus = 'page-heading' | 'preserve';

interface NavigationOptions {
  history?: NavigationHistory;
  focus?: NavigationFocus;
}

export type NavigationIntent =
  | ({ to: 'home' } & NavigationOptions)
  | ({ to: 'review-queue' } & NavigationOptions)
  | ({ to: 'record-detail'; recordId: string } & NavigationOptions)
  | ({ to: 'record-new' } & NavigationOptions)
  | ({ to: 'record-history' } & NavigationOptions)
  | ({ to: 'notifications' } & NavigationOptions)
  | ({ to: 'audio-jobs' } & NavigationOptions)
  | ({ to: 'children' } & NavigationOptions)
  | ({ to: 'voice-consent' } & NavigationOptions)
  | ({ to: 'school-settings' } & NavigationOptions)
  | ({ to: 'teachers' } & NavigationOptions)
  | ({ to: 'edge-devices' } & NavigationOptions)
  | ({ to: 'runtime-readiness' } & NavigationOptions)
  | ({ to: 'audit-events' } & NavigationOptions);

export function normalizeNavigationIntent(
  intent: NavigationIntent
): Required<NavigationOptions> & NavigationIntent {
  return {
    history: intent.history ?? 'push',
    focus: intent.focus ?? 'page-heading',
    ...intent
  };
}
