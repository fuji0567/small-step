import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

function source(path: string): string {
  return readFileSync(resolve(process.cwd(), path), 'utf8');
}

describe('accessibility layout contracts', () => {
  it('keeps readable body text and a forced-colors focus fallback', () => {
    const appCss = source('src/app.css');

    expect(appCss).toMatch(/body\s*{[^}]*line-height:\s*1\.7;/s);
    expect(appCss).toMatch(/@media\s*\(forced-colors:\s*active\)/);
    expect(appCss).toMatch(
      /@media\s*\(forced-colors:\s*active\)[\s\S]*outline:\s*2px solid Highlight !important;/
    );
    expect(appCss).toMatch(
      /@media\s*\(forced-colors:\s*active\)[\s\S]*box-shadow:\s*none !important;/
    );
  });

  it.each(['LoginPanel.svelte', 'BootstrapPanel.svelte'])(
    '%s keeps its bounded panel inside a narrow viewport',
    (name) => {
      const panel = source(`src/lib/features/teacher-shell/${name}`);

      expect(panel).toMatch(
        /section\s*{[^}]*width:\s*min\(100%, 32rem\);[^}]*box-sizing:\s*border-box;/s
      );
    }
  );

  it('limits user-authored record and notification text to a readable measure', () => {
    expect(source('src/lib/features/records/records.css')).toMatch(
      /\.records-card\s*>\s*p\s*{[^}]*max-width:\s*40em;/s
    );
    expect(source('src/lib/features/notifications/notifications.css')).toMatch(
      /\.notification-content\s+p\s*{[^}]*max-width:\s*40em;/s
    );
  });
});
