import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    paths: {
      relative: false
    },
    adapter: adapter({
      pages: '../app/frontend_dist',
      assets: '../app/frontend_dist',
      fallback: '200.html',
      strict: true
    })
  }
};

export default config;
