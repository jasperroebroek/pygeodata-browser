<script lang="ts">
  import { layout, setPaneWidth } from '../lib/stores.svelte';
  import type { PaneKey } from '../lib/stores.svelte';

  /** Sits on the `edge` border of its (position: relative) pane; drag to resize, double-click to reset. */
  let { pane, edge, min, max }: { pane: PaneKey; edge: 'left' | 'right'; min: number; max: () => number } = $props();

  let dragging = $state(false);

  function down(e: PointerEvent) {
    e.preventDefault();
    const handle = e.currentTarget as HTMLElement;
    const paneEl = handle.parentElement!;
    handle.setPointerCapture(e.pointerId);
    dragging = true;
    const startX = e.clientX;
    const startW = paneEl.getBoundingClientRect().width;
    const move = (ev: PointerEvent) => {
      const d = ev.clientX - startX;
      layout.widths[pane] = Math.round(Math.max(min, Math.min(max(), startW + (edge === 'right' ? d : -d))));
    };
    const up = () => {
      dragging = false;
      handle.removeEventListener('pointermove', move);
      handle.removeEventListener('pointerup', up);
      setPaneWidth(pane, layout.widths[pane]);
    };
    handle.addEventListener('pointermove', move);
    handle.addEventListener('pointerup', up);
  }
</script>

<div
  class="resizer resizer--{edge}"
  class:dragging
  role="separator"
  aria-orientation="vertical"
  aria-label="Resize pane"
  title="Drag to resize, double-click to reset"
  onpointerdown={down}
  ondblclick={() => setPaneWidth(pane, null)}
></div>

<style>
  .resizer {
    position: absolute;
    top: 0;
    bottom: 0;
    width: 7px;
    cursor: col-resize;
    z-index: 20;
    touch-action: none;
  }
  .resizer--right {
    right: 0;
  }
  .resizer--left {
    left: 0;
  }
  /* Highlight drawn over the pane's own border */
  .resizer::after {
    content: '';
    position: absolute;
    top: 0;
    bottom: 0;
    width: 3px;
    transition: background 0.12s;
  }
  .resizer--right::after {
    right: 0;
  }
  .resizer--left::after {
    left: 0;
  }
  .resizer:hover::after,
  .resizer.dragging::after {
    background: var(--accent);
  }
  :global(body:has(.resizer.dragging)) {
    cursor: col-resize;
    user-select: none;
  }
</style>
