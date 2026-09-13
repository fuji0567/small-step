import js from '@eslint/js';
import prettier from 'eslint-config-prettier';
import svelte from 'eslint-plugin-svelte';
import globals from 'globals';
import ts from 'typescript-eslint';

export default ts.config(
  { ignores: ['.svelte-kit/**', 'coverage/**', 'node_modules/**'] },
  js.configs.recommended,
  ...ts.configs.recommended,
  ...svelte.configs.recommended,
  {
    languageOptions: {
      globals: { ...globals.browser, ...globals.node }
    }
  },
  {
    files: ['**/*.ts'],
    languageOptions: {
      parser: ts.parser
    }
  },
  {
    files: ['**/*.svelte.ts'],
    languageOptions: {
      parser: ts.parser
    },
    rules: {
      // Callback registries and other non-UI collections do not need Svelte's
      // reactive collection wrappers merely because they live in a rune module.
      'svelte/prefer-svelte-reactivity': 'off'
    }
  },
  {
    files: ['**/*.svelte'],
    languageOptions: {
      parserOptions: {
        parser: ts.parser
      }
    }
  },
  prettier
);
