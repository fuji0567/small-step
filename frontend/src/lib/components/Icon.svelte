<script lang="ts">
  import type { IconName } from './types';

  type SharedProps = {
    name: IconName;
    size?: 20 | 24;
    class?: string;
  };

  type Props = SharedProps &
    (
      | { decorative?: true; label?: never }
      | { decorative: false; label: string }
    );

  let {
    name,
    size = 20,
    label,
    decorative = true,
    class: className = ''
  }: Props = $props();
</script>

<svg
  class={`ss-icon ${className}`.trim()}
  width={size}
  height={size}
  viewBox="0 0 24 24"
  fill="none"
  stroke="currentColor"
  stroke-width="2"
  stroke-linecap="round"
  stroke-linejoin="round"
  aria-hidden={decorative ? 'true' : undefined}
  aria-label={!decorative ? label : undefined}
  role={!decorative ? 'img' : undefined}
  focusable="false"
>
  {#if name === 'home'}
    <path d="M3 10.5 12 3l9 7.5" />
    <path d="M5 9.5V21h14V9.5M9 21v-7h6v7" />
  {:else if name === 'review' || name === 'checklist'}
    <path d="M9 5h11M9 12h11M9 19h11" />
    <path d="m3 5 1.5 1.5L7 3.5M3 12l1.5 1.5L7 10.5M3 19l1.5 1.5L7 17.5" />
  {:else if name === 'history'}
    <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
    <path d="M3 3v5h5M12 7v5l3 2" />
  {:else if name === 'notifications'}
    <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" />
    <path d="M10 21h4" />
  {:else if name === 'audio'}
    <path d="M4 10v4M8 7v10M12 4v16M16 7v10M20 10v4" />
  {:else if name === 'child'}
    <circle cx="12" cy="8" r="4" />
    <path d="M5 21a7 7 0 0 1 14 0M9 8h.01M15 8h.01M10 10.5c1.3 1 2.7 1 4 0" />
  {:else if name === 'schedule'}
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  {:else if name === 'group'}
    <circle cx="9" cy="8" r="3" />
    <circle cx="17" cy="9" r="2" />
    <path d="M3 20a6 6 0 0 1 12 0M14 15a5 5 0 0 1 7 4.5" />
  {:else if name === 'microphone'}
    <rect x="9" y="3" width="6" height="11" rx="3" />
    <path d="M5 11a7 7 0 0 0 14 0M12 18v3M9 21h6" />
  {:else if name === 'privacy'}
    <path d="M12 3 5 6v5c0 4.7 2.8 8.3 7 10 4.2-1.7 7-5.3 7-10V6l-7-3Z" />
    <path d="M9.5 11.5 11 13l3.5-4" />
  {:else if name === 'login'}
    <path d="M14 8l4 4-4 4M18 12H7" />
    <path d="M11 4H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h6" />
  {:else if name === 'logout'}
    <path d="m10 8-4 4 4 4M6 12h11" />
    <path d="M13 4h6a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-6" />
  {:else if name === 'refresh'}
    <path d="M20 7v5h-5M4 17v-5h5" />
    <path d="M6.1 9A7 7 0 0 1 18 6l2 1M18 15a7 7 0 0 1-12 3l-2-1" />
  {:else if name === 'success'}
    <circle cx="12" cy="12" r="9" />
    <path d="m8 12 2.5 2.5L16 9" />
  {:else if name === 'warning'}
    <path d="M12 3 2.5 20h19L12 3Z" />
    <path d="M12 9v4M12 17h.01" />
  {:else if name === 'error'}
    <circle cx="12" cy="12" r="9" />
    <path d="m9 9 6 6M15 9l-6 6" />
  {:else if name === 'close'}
    <path d="m6 6 12 12M18 6 6 18" />
  {:else}
    <circle cx="12" cy="12" r="9" />
    <path d="M12 11v6M12 7h.01" />
  {/if}
</svg>

<style>
  .ss-icon {
    display: inline-block;
    flex: 0 0 auto;
    color: currentColor;
    vertical-align: middle;
  }
</style>
