<script lang="ts">
  import { ui } from '../lib/stores.svelte';

  /** Thin progress strip along the top edge of its (position: relative) pane during reloads. */
  const visible = $derived((ui.loading && ui.statusKnown && !ui.overlay) || ui.reconciling);

</script>

{#if visible}
  <div class="reload-bar" role="progressbar" title="Loading entries…">
    <div class="reload-bar-fill"></div>
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
