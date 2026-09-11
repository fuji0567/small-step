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
    { href: '/teacher-next/', label: 'ホーム', icon: 'home' },
    {
      href: '/teacher-next/review/',
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
      currentPath: '/teacher-next/review/record-1/',
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
      currentPath: '/teacher-next/',
      busy: true,
      children: textSnippet('<p>今日の状況</p>')
    });

    expect(screen.getByRole('main')).toHaveAttribute('aria-busy', 'true');
    expect(
      screen.getByRole('status', { name: '読み込み中です' })
    ).toBeInTheDocument();
  });
});
