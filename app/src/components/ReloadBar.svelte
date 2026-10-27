<script lang="ts">
  import { ui } from '../lib/stores.svelte';

  /** Thin progress strip along the top edge of its (position: relative) pane during reloads. */
  const visible = $derived((ui.loading && ui.statusKnown && !ui.overlay) || ui.reconciling);

  // Null while there is no measurable progress (reconcile, or a reload that has not reported yet).
  const pct = $derived.by(() => {
    if (!ui.loading) return null;
    const p = ui.progress;
    const total = (p.reimport_total ?? 0) + (p.total ?? 0);
    return total ? Math.round((((p.reimport_done ?? 0) + (p.done ?? 0)) / total) * 100) : null;
  });
</script>

{#if visible}
  <div
    class="reload-bar"
    role="progressbar"
    aria-valuenow={pct ?? undefined}
    title={ui.reimporting ? 'Reimporting Python files…' : 'Loading entries…'}
  >
    <div class="reload-bar-fill" class:indeterminate={pct === null} style:width={pct === null ? null : `${pct}%`}></div>
  </div>
{/if}

<style>
  .reload-bar {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    z-index: 30;
    overflow: hidden;
    background: var(--accent-bg);
  }
  .reload-bar-fill {
    height: 100%;
    background: var(--accent);
    transition: width 0.25s ease;
  }
  .reload-bar-fill.indeterminate {
    width: 30%;
    animation: slide 1.1s ease-in-out infinite;
  }
  @keyframes slide {
    from {
      transform: translateX(-100%);
    }
    to {
      transform: translateX(340%);
    }
  }
</style>
