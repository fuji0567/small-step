import { readFileSync, readdirSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

const componentDirectory = resolve(process.cwd(), 'src/lib/components');
const componentSources = readdirSync(componentDirectory)
  .filter((name) => name.endsWith('.svelte'))
  .map(
    (name) =>
      [name, readFileSync(resolve(componentDirectory, name), 'utf8')] as const
  );

describe('shared component source contract', () => {
  it.each(componentSources)(
    '%s uses Svelte 5 runes without legacy or unsafe rendering',
    (_name, source) => {
      expect(source).not.toMatch(
        /export\s+let|\$:\s|on:click|createEventDispatcher|<slot|\{@html/
      );
      expect(source).toContain('$props');
    }
  );

  it.each(componentSources)(
    '%s does not load external assets',
    (_name, source) => {
      expect(source).not.toMatch(/https?:\/\/|@font-face|url\s*\(/i);
    }
  );
});
