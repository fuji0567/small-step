import { describe, expect, it, vi } from 'vitest';

import { AppController } from './app-controller';
import { HOME_DERIVED_SCOPES, normalizeNavigationIntent } from './contracts';
import { SchoolContext, type SchoolSummary } from './school-context.svelte';

const school = (id: string): SchoolSummary => ({
  id,
  name: `園 ${id}`,
  timezone: 'Asia/Tokyo',
  digest_time: '17:00',
  created_at: '2026-09-11T00:00:00Z'
});

describe('SchoolContext', () => {
  it('園が実際に変わったときだけ登録済みstateを初期化する', () => {
    const context = new SchoolContext();
    const reset = vi.fn();
    context.setSchools([school('a'), school('b')]);
    const unregister = context.onSchoolChangeReset(reset);

    context.selectSchool('a');
    context.selectSchool('a');
    context.selectSchool('b');

    expect(context.schoolId).toBe('b');
    expect(context.selectedSchool?.id).toBe('b');
    expect(reset.mock.calls).toEqual([['a'], ['b']]);

    unregister();
    context.selectSchool(null);
    expect(reset).toHaveBeenCalledTimes(2);
  });

  it('候補から消えた園を解除し、未知の園は選べない', () => {
    const context = new SchoolContext();
    const reset = vi.fn();
    context.setSchools([school('a')]);
    context.onSchoolChangeReset(reset);
    context.selectSchool('a');

    context.setSchools([]);
    expect(context.schoolId).toBeNull();
    expect(reset).toHaveBeenLastCalledWith(null);
    expect(() => context.selectSchool('missing')).toThrow(RangeError);
  });
});

describe('NavigationIntent', () => {
  it('URL履歴とfocusの既定を一貫させ、recordIdを型付きで保持する', () => {
    expect(
      normalizeNavigationIntent({ to: 'record-detail', recordId: 'r1' })
    ).toEqual({
      to: 'record-detail',
      recordId: 'r1',
      history: 'push',
      focus: 'page-heading'
    });
    expect(
      normalizeNavigationIntent({
        to: 'home',
        history: 'replace',
        focus: 'preserve'
      })
    ).toEqual({
      to: 'home',
      history: 'replace',
      focus: 'preserve'
    });
  });

  it('homeの件数が依存するrefresh scopeを公開する', () => {
    expect(HOME_DERIVED_SCOPES).toEqual([
      'records',
      'notifications',
      'children',
      'invitations',
      'audioJobs'
    ]);
  });
});

describe('AppController', () => {
  it('1回のrefreshに重複scopeがあっても一度だけ取得する', async () => {
    const controller = new AppController();
    const records = vi.fn();
    const notifications = vi.fn();
    controller.register('records', records);
    controller.register('notifications', notifications);

    await controller.refresh(['records', 'records', 'notifications']);

    expect(records).toHaveBeenCalledOnce();
    expect(notifications).toHaveBeenCalledOnce();
  });

  it('同じscopeの並行refreshを共有し、完了後は再取得できる', async () => {
    const controller = new AppController();
    let finish: (() => void) | undefined;
    const records = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          finish = resolve;
        })
    );
    controller.register('records', records);

    const first = controller.refresh(['records']);
    const second = controller.refresh(['records']);
    await vi.waitFor(() => expect(records).toHaveBeenCalledOnce());
    finish?.();
    await Promise.all([first, second]);

    const third = controller.refresh(['records']);
    await vi.waitFor(() => expect(records).toHaveBeenCalledTimes(2));
    finish?.();
    await third;
  });

  it('handlerの重複登録と未登録scopeを明示的に拒否する', async () => {
    const controller = new AppController();
    controller.register('records', vi.fn());

    expect(() => controller.register('records', vi.fn())).toThrow(
      'already registered'
    );
    await expect(controller.refresh(['notifications'])).rejects.toThrow(
      'not registered'
    );
  });
});
