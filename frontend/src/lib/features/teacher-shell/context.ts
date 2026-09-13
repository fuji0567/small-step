import { getContext, setContext } from 'svelte';

import type { TeacherShellState } from './teacher-shell.svelte';

const TEACHER_SHELL_CONTEXT = Symbol('teacher-shell');

export function provideTeacherShell(state: TeacherShellState): void {
  setContext(TEACHER_SHELL_CONTEXT, state);
}

export function useTeacherShell(): TeacherShellState {
  const state = getContext<TeacherShellState>(TEACHER_SHELL_CONTEXT);
  if (!state) throw new Error('Teacher shell context is not available');
  return state;
}
