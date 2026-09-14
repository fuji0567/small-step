import type { Pathname } from '$app/types';
import type { Snippet } from 'svelte';

export type IconName =
  | 'home'
  | 'review'
  | 'history'
  | 'notifications'
  | 'audio'
  | 'child'
  | 'schedule'
  | 'group'
  | 'microphone'
  | 'checklist'
  | 'privacy'
  | 'login'
  | 'logout'
  | 'refresh'
  | 'info'
  | 'success'
  | 'warning'
  | 'error'
  | 'close';

export type SemanticTone = 'info' | 'success' | 'warning' | 'error';

export type AppShellNavItem = {
  href: Pathname;
  label: string;
  icon?: IconName;
  badge?: string;
  badgeAriaLabel?: string;
  badgeTone?: 'default' | 'warning';
  guide?: string;
};

export type OptionalSnippet = Snippet | undefined;
