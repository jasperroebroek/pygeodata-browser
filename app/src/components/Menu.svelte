<script lang="ts">
  import { api } from '../lib/api';
  import { app, pollStatus } from '../lib/stores.svelte';
  import { toast } from './detail/toast.svelte';
  import CleanModal from './menu/CleanModal.svelte';

  let open = $state(false);
  let wrapEl: HTMLElement | null = $state(null);
  // Live-classes flag mirrors legacy hasLiveClasses (fetched from /api/status).
  let hasLive = $state(false);
  let cleanModal = $state<null | 'cache' | 'source'>(null);

  const noPayload = $derived(app.payload === null);

  async function toggleMenu(): Promise<void> {
    open = !open;
    if (open) {
      try {
        hasLive = (await api.status()).has_live_classes;
      } catch {
        /* keep last known value */
      }
    }
  }

  function onWindowClick(e: MouseEvent): void {
    if (open && wrapEl && !wrapEl.contains(e.target as Node)) open = false;
  }

  function onKeydown(e: KeyboardEvent): void {
    if (e.key === 'Escape' && open) open = false;
  }

  async function reload(reimport: boolean): Promise<void> {
    open = false;
    try {
      await api.rebuild(reimport);
      app.loading = true;
      app.ready = false;
      pollStatus();
    } catch (err) {
      toast(`${reimport ? 'Reimport' : 'Reload'} failed: ${err}`);
    }
  }

  function openClean(kind: 'cache' | 'source'): void {
    open = false;
    cleanModal = kind;
  }
</script>

<svelte:window onclick={onWindowClick} onkeydown={onKeydown} />

<div class="wrap" bind:this={wrapEl}>
  <button class="icon" title="Menu" aria-haspopup="menu" aria-expanded={open} onclick={toggleMenu}>
    ⋮
  </button>

  {#if open}
    <div class="menu" role="menu">
      <button class="item" role="menuitem" disabled={noPayload} onclick={() => void reload(false)}>
        Reload from disk
      </button>
      <button class="item" role="menuitem" disabled={noPayload} onclick={() => void reload(true)}>
        Reimport Python files
      </button>
      <div class="sep"></div>
      <button
        class="item"
        role="menuitem"
        disabled={noPayload || !hasLive}
        onclick={() => openClean('cache')}
      >
        Clean cache…
      </button>
      <button
        class="item"
        role="menuitem"
        disabled={noPayload || !hasLive}
        onclick={() => openClean('source')}
      >
        Clean registry…
      </button>
    </div>
  {/if}
</div>

{#if cleanModal}
  <CleanModal kind={cleanModal} onClose={() => (cleanModal = null)} />
{/if}

<style>
  .wrap {
    position: relative;
    display: flex;
  }

  .icon {
    width: 28px;
    height: 28px;
    border-radius: var(--r-sm);
    color: var(--text-2);
    font-size: var(--fs-md);
    line-height: 1;
  }

  .icon:hover {
    background: var(--bg-hover);
  }

  .menu {
    position: absolute;
    top: calc(100% + 4px);
    right: 0;
    z-index: 60;
    min-width: 180px;
    padding: var(--s-1);
    background: var(--bg-elev);
    border: 1px solid var(--border-strong);
    border-radius: var(--r-md);
    box-shadow: var(--shadow-md);
    display: flex;
    flex-direction: column;
  }

  .item {
    padding: var(--s-1) var(--s-2);
    border-radius: var(--r-sm);
    text-align: left;
    font-size: var(--fs-sm);
    color: var(--text);
    white-space: nowrap;
  }

  .item:hover:not(:disabled) {
    background: var(--bg-hover);
  }

  .item:disabled {
    color: var(--text-3);
    cursor: default;
  }

  .sep {
    height: 1px;
    margin: var(--s-1) 0;
    background: var(--border);
  }
</style>
