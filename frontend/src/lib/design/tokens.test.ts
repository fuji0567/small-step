import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const tokensPath = resolve(process.cwd(), 'src/lib/design/tokens.css');
const tokens = readFileSync(tokensPath, 'utf8');

function token(name: string): string {
  const match = tokens.match(
    new RegExp(`--${name}:\\s*(#[0-9a-f]{6}|[0-9.]+rem)`)
  );
  if (!match) throw new Error(`Missing token: ${name}`);
  return match[1];
}

function relativeLuminance(hex: string): number {
  const channels = [1, 3, 5].map(
    (offset) => Number.parseInt(hex.slice(offset, offset + 2), 16) / 255
  );
  const linear = channels.map((value) =>
    value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
  );
  return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
}

function contrast(foreground: string, background: string): number {
  const values = [
    relativeLuminance(foreground),
    relativeLuminance(background)
  ].sort((left, right) => right - left);
  return (values[0] + 0.05) / (values[1] + 0.05);
}

describe('DADS design tokens', () => {
  it('uses only the five agreed 8px spacing steps', () => {
    expect([
      token('ss-space-1'),
      token('ss-space-2'),
      token('ss-space-3'),
      token('ss-space-4'),
      token('ss-space-5')
    ]).toEqual(['0.5rem', '1rem', '1.5rem', '2rem', '3rem']);
  });

  it.each([
    ['text', 'ss-color-text', 'ss-color-surface', 4.5],
    ['muted text', 'ss-color-text-muted', 'ss-color-surface', 4.5],
    ['action label', 'ss-color-surface', 'ss-color-action', 4.5],
    [
      'success text',
      'ss-color-success-text',
      'ss-color-success-background',
      4.5
    ],
    [
      'warning text',
      'ss-color-warning-text',
      'ss-color-warning-background',
      4.5
    ],
    ['error text', 'ss-color-error-text', 'ss-color-error-background', 4.5],
    ['surface border', 'ss-color-border', 'ss-color-surface', 3],
    ['page border', 'ss-color-border', 'ss-color-page', 3],
    [
      'success border',
      'ss-color-success-border',
      'ss-color-success-background',
      3
    ],
    [
      'warning border',
      'ss-color-warning-border',
      'ss-color-warning-background',
      3
    ],
    ['error border', 'ss-color-error-border', 'ss-color-error-background', 3]
  ])(
    '%s meets its minimum contrast',
    (_label, foreground, background, minimum) => {
      expect(
        contrast(token(foreground), token(background))
      ).toBeGreaterThanOrEqual(minimum);
    }
  );

  it('keeps the immutable DADS focus colors', () => {
    expect(token('ss-color-focus-inner')).toBe('#ffd43d');
    expect(token('ss-color-focus-outer')).toBe('#000000');
  });
});
