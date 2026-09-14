import { fireEvent, render, screen, waitFor } from '@testing-library/svelte';
import { createRawSnippet } from 'svelte';
import { afterEach, describe, expect, it, vi } from 'vitest';

import AppShell from './AppShell.svelte';
import Button from './Button.svelte';
import ConfirmDialog from './ConfirmDialog.svelte';
import Icon from './Icon.svelte';
import Loading from './Loading.svelte';
import Notice from './Notice.svelte';
import StatusBadge from './StatusBadge.svelte';
import type { AppShellNavItem } from './types';

const textSnippet = (text: string) =>
  createRawSnippet(() => ({ render: () => text }));

afterEach(() => {
  document.body.innerHTML = '';
});

describe('Icon', () => {
  it('hides decorative icons from assistive technology', () => {
    const { container } = render(Icon, { name: 'home' });
    const icon = container.querySelector('svg');

    expect(icon).toHaveAttribute('aria-hidden', 'true');
    expect(icon).toHaveAttribute('focusable', 'false');
  });

  it('exposes a supplied label for meaningful icons', () => {
    render(Icon, { name: 'warning', decorative: false, label: '注意' });

    expect(screen.getByRole('img', { name: '注意' })).toBeInTheDocument();
  });
});

describe('Button', () => {
  it('uses type button and forwards native click handlers', async () => {
    const onclick = vi.fn();
    render(Button, { children: textSnippet('保存'), onclick });

    const button = screen.getByRole('button', { name: '保存' });
    expect(button).toHaveAttribute('type', 'button');
    await fireEvent.click(button);
    expect(onclick).toHaveBeenCalledOnce();
  });

  it('disables interaction and reports a busy operation', () => {
    render(Button, { children: textSnippet('保存'), loading: true });

    const button = screen.getByRole('button', { name: '保存' });
    expect(button).toBeDisabled();
    expect(button).toHaveAttribute('aria-busy', 'true');
  });

  it('describes a guided button without changing its accessible name', () => {
    const existingDescription = document.createElement('p');
    existingDescription.id = 'existing-description';
    existingDescription.textContent = '既存の説明です。';
    document.body.append(existingDescription);

    render(Button, {
      children: textSnippet('承認する'),
      guide: '保護者への通知を準備します。',
      'aria-describedby': existingDescription.id
    });

    const button = screen.getByRole('button', { name: '承認する' });
    const tooltip = screen.getByRole('tooltip', { hidden: true });
    expect(button).toHaveAccessibleName('承認する');
    expect(button).toHaveAttribute(
      'aria-describedby',
      `${existingDescription.id} ${tooltip.id}`
    );
    expect(button).toHaveAccessibleDescription(
      '既存の説明です。 保護者への通知を準備します。'
    );
  });

  it('uses a unique guide id and leaves unguided button markup unwrapped', () => {
    const first = render(Button, {
      children: textSnippet('承認する'),
      guide: '通知を準備します。'
    });
    const second = render(Button, {
      children: textSnippet('却下する'),
      guide: '確認待ちから外します。'
    });
    const describedIds = screen
      .getAllByRole('button')
      .map((button) => button.getAttribute('aria-describedby'));

    expect(describedIds[0]).toBeTruthy();
    expect(describedIds[1]).toBeTruthy();
    expect(describedIds[0]).not.toBe(describedIds[1]);

    first.unmount();
    second.unmount();
    const unguided = render(Button, { children: textSnippet('保存') });
    expect(unguided.container.firstElementChild).toBe(
      screen.getByRole('button', { name: '保存' })
    );
    expect(screen.queryByRole('tooltip', { hidden: true })).toBeNull();
  });

  it('dismisses a visible guide with Escape and allows a later trigger', async () => {
    render(Button, {
      children: textSnippet('承認する'),
      guide: '通知を準備します。'
    });

    const button = screen.getByRole('button', { name: '承認する' });
    const guide = screen.getByRole('tooltip', { hidden: true });
    const wrapper = guide.parentElement;

    expect(wrapper).not.toBeNull();
    await fireEvent.focusIn(button);
    await fireEvent.keyDown(button, { key: 'Escape' });
    expect(wrapper).toHaveClass('ss-button-guide--dismissed');

    await fireEvent.focusOut(button, { relatedTarget: document.body });
    await fireEvent.pointerEnter(wrapper!);
    expect(wrapper).not.toHaveClass('ss-button-guide--dismissed');
  });
});

describe('Notice', () => {
  it('announces asynchronous errors assertively', () => {
    render(Notice, {
      tone: 'error',
      title: '保存できませんでした',
      children: textSnippet('通信状況を確認してください。')
    });

    expect(screen.getByRole('alert')).toHaveTextContent('保存できませんでした');
    expect(screen.getByRole('alert')).toHaveTextContent(
      '通信状況を確認してください。'
    );
  });

  it('uses a polite status for non-error notices', () => {
    render(Notice, {
      tone: 'success',
      children: textSnippet('保存しました。')
    });

    expect(screen.getByRole('status')).toHaveAttribute('aria-live', 'polite');
  });
});

describe('Loading', () => {
  it('uses the existing Japanese loading message by default', () => {
    render(Loading);

    expect(
      screen.getByRole('status', { name: '読み込み中です' })
    ).toHaveTextContent('読み込み中です');
  });

  it('renders nothing while inactive', () => {
    render(Loading, { active: false });

    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });
});

describe('StatusBadge', () => {
  it('keeps the compact visual label and exposes its full meaning', () => {
    render(StatusBadge, {
      label: '！3件',
      ariaLabel: '送信失敗3件',
      tone: 'error'
    });

    expect(screen.getByLabelText('送信失敗3件')).toHaveTextContent('！3件');
  });

  it('opts into polite announcements only when requested', async () => {
    const { rerender } = render(StatusBadge, { label: '確認済み' });
    expect(screen.queryByRole('status')).not.toBeInTheDocument();

    await rerender({ label: '確認済み', live: true });
    expect(screen.getByRole('status')).toHaveAttribute('aria-live', 'polite');
  });
});

describe('ConfirmDialog', () => {
  it('focuses cancel first, cancels with Escape, and restores focus', async () => {
    const trigger = document.createElement('button');
    trigger.textContent = '削除を開く';
    document.body.append(trigger);
    trigger.focus();
    const onCancel = vi.fn();

    const { rerender } = render(ConfirmDialog, {
      open: true,
      title: '削除しますか？',
      description: 'この操作は取り消せません。',
      confirmLabel: '削除する',
      onCancel
    });

    const dialog = screen.getByRole('dialog', { name: '削除しますか？' });
    const cancel = screen.getByRole('button', { name: 'キャンセル' });
    await waitFor(() => expect(cancel).toHaveFocus());

    await fireEvent(dialog, new Event('cancel', { cancelable: true }));
    expect(onCancel).toHaveBeenCalledOnce();
    await rerender({
      open: false,
      title: '削除しますか？',
      description: 'この操作は取り消せません。',
      confirmLabel: '削除する',
      onCancel
    });
    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it('prevents dismissal and actions while busy', async () => {
    const onCancel = vi.fn();
    const onConfirm = vi.fn();
    render(ConfirmDialog, {
      open: true,
      title: '処理を確認',
      busy: true,
      onCancel,
      onConfirm
    });

    const dialog = screen.getByRole('dialog', { name: '処理を確認' });
    expect(dialog).toHaveAttribute('aria-busy', 'true');
    expect(screen.getByRole('button', { name: 'キャンセル' })).toBeDisabled();
    expect(screen.getByRole('button', { name: '処理中です' })).toBeDisabled();
    await fireEvent(dialog, new Event('cancel', { cancelable: true }));
    expect(onCancel).not.toHaveBeenCalled();
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it('runs the confirmation callback from the explicit action', async () => {
    const onConfirm = vi.fn();
    render(ConfirmDialog, {
      open: true,
      title: '承認しますか？',
      confirmLabel: '承認する',
      onConfirm
    });

    await fireEvent.click(screen.getByRole('button', { name: '承認する' }));
    expect(onConfirm).toHaveBeenCalledOnce();
  });
});

describe('AppShell', () => {
  const navItems: AppShellNavItem[] = [
    { href: '/teacher/', label: 'ホーム', icon: 'home' },
    {
      href: '/teacher/review/',
      label: 'レビュー待ち',
      icon: 'review',
      badge: '3件',
      badgeAriaLabel: 'レビュー待ち3件'
    }
  ];

  it('provides landmarks, one heading, URL navigation, and a skip link', () => {
    render(AppShell, {
      title: '先生用',
      eyebrow: 'スモールステップ',
      navItems,
      currentPath: '/teacher/review/record-1/',
      children: textSnippet('<h2>記録の詳細</h2>')
    });

    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
    expect(
      screen.getByRole('navigation', { name: '先生用メニュー' })
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /レビュー待ち/ })).toHaveAttribute(
      'aria-current',
      'page'
    );
    expect(screen.getByRole('link', { name: '本文へ移動' })).toHaveAttribute(
      'href',
      '#main-content'
    );
    expect(screen.getByRole('main')).toHaveAttribute('id', 'main-content');
  });

  it('marks the main area busy and exposes the loading status', () => {
    render(AppShell, {
      title: '先生用',
      navItems,
      currentPath: '/teacher/',
      busy: true,
      children: textSnippet('<p>今日の状況</p>')
    });

    expect(screen.getByRole('main')).toHaveAttribute('aria-busy', 'true');
    expect(
      screen.getByRole('status', { name: '読み込み中です' })
    ).toBeInTheDocument();
  });

  it('renders default and warning badge tones without changing their labels', () => {
    render(AppShell, {
      title: '先生用',
      navItems: [
        {
          href: '/teacher/review/',
          label: 'レビュー待ち',
          badge: '3件',
          badgeAriaLabel: 'レビュー待ち3件'
        },
        {
          href: '/teacher/notifications/',
          label: '通知',
          badge: '!99+',
          badgeTone: 'warning',
          badgeAriaLabel: '未処理通知99件以上'
        },
        {
          href: '/teacher/history/',
          label: '履歴',
          badge: '999+'
        },
        { href: '/teacher/children/', label: '園児' }
      ],
      currentPath: '/teacher/',
      children: textSnippet('<p>今日の状況</p>')
    });

    const defaultBadge = screen.getByText('3件');
    expect(defaultBadge).toHaveClass(
      'ss-app-shell__badge',
      'ss-app-shell__badge--default'
    );
    expect(defaultBadge).toHaveAttribute('aria-label', 'レビュー待ち3件');

    const warningBadge = screen.getByText('!99+');
    expect(warningBadge).toHaveClass(
      'ss-app-shell__badge',
      'ss-app-shell__badge--warning'
    );
    expect(warningBadge).toHaveAttribute('aria-label', '未処理通知99件以上');
    expect(warningBadge).toHaveTextContent('!99+');

    const visibleOnlyBadge = screen.getByText('999+');
    expect(visibleOnlyBadge).not.toHaveAttribute('aria-label');
    expect(screen.getByRole('link', { name: '履歴 999+' })).toBeInTheDocument();

    const childrenLink = screen.getByRole('link', { name: '園児' });
    expect(childrenLink.querySelector('.ss-app-shell__badge')).toBeNull();
  });

  it('uses the full badge aria-label once as the link accessible name', () => {
    render(AppShell, {
      title: '先生用',
      navItems: [
        {
          href: '/teacher/review/',
          label: 'レビュー待ち',
          badge: '3件',
          badgeAriaLabel: 'レビュー待ち3件'
        }
      ],
      currentPath: '/teacher/',
      children: textSnippet('<p>今日の状況</p>')
    });

    expect(
      screen.getByRole('link', { name: 'レビュー待ち レビュー待ち3件' })
    ).toBeInTheDocument();
    expect(
      screen.queryByRole('link', { name: 'レビュー待ち 3件 レビュー待ち3件' })
    ).not.toBeInTheDocument();
  });
});
