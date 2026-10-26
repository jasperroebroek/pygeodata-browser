<script lang="ts">
  import { app, reloadState, setKindFilter, setRowDisplay, toggleTheme } from '../lib/stores.svelte';
  import type { KindFilter } from '../lib/stores.svelte';

  const kinds: { key: KindFilter; label: string }[] = [
    { key: 'all', label: 'All' },
    { key: 'Data', label: 'Data' },
    { key: 'Table', label: 'Tables' },
    { key: 'Figure', label: 'Figures' },
  ];

  const views: { key: 'entries' | 'code' | 'export'; label: string }[] = [
    { key: 'entries', label: 'Entries' },
    { key: 'code', label: 'Code' },
    { key: 'export', label: 'Export' },
  ];

  function setView(view: 'entries' | 'code' | 'export') {
    app.view = view;
  }
</script>

<header class="topbar">
  <nav class="views">
    {#each views as v}
      <button class:active={app.view === v.key} onclick={() => setView(v.key)}>{v.label}</button>
    {/each}
  </nav>

  {#if app.view === 'entries'}
    <nav class="kinds">
      {#each kinds as k}
        <button class:active={app.kindFilter === k.key} onclick={() => setKindFilter(k.key)}>{k.label}</button>
      {/each}
    </nav>
  {/if}

  <div class="spacer"></div>

  {#if app.view === 'entries'}
    <button
      class="toggle"
      class:active={app.rowDisplay === 'all'}
      title="Show parameter rows inside the entries table"
      onclick={() => setRowDisplay(app.rowDisplay === 'all' ? 'none' : 'all')}
    >
      Detailed
    </button>
  {/if}

  <span class="counts mono">
    {#if app.payload}
      {app.payload.counts.visible_entries}/{app.payload.counts.entries} shown
    {:else if app.bootstrap.length}
      {app.bootstrap.length} classes (bootstrap)
    {/if}
  </span>

  <button class="icon" onclick={reloadState} title="Reload state">⟳</button>
  <button class="icon" onclick={toggleTheme} title="Toggle theme">◐</button>
</header>

<style>
  .topbar {
    display: flex;
    align-items: center;
    gap: var(--s-3);
    height: var(--topbar-h);
    padding: 0 var(--s-3);
    border-bottom: 1px solid var(--border);
    background: var(--bg-sidebar);
    flex: none;
  }

  nav {
    display: flex;
    gap: 2px;
  }

  nav button {
    padding: 4px 10px;
    border-radius: var(--r-sm);
    color: var(--text-2);
    font-size: var(--fs-sm);
  }

  nav button:hover {
    background: var(--bg-hover);
  }

  nav button.active {
    background: var(--bg-active);
    color: var(--text);
    font-weight: 500;
  }

  .kinds {
    margin-left: var(--s-2);
  }

  .spacer {
    flex: 1;
  }

  .toggle {
    padding: 4px 10px;
    border-radius: var(--r-full);
    font-size: var(--fs-sm);
    color: var(--text-2);
    border: 1px solid var(--border-strong);
  }

  .toggle.active {
    background: var(--accent-soft);
    color: var(--accent-text);
    border-color: transparent;
  }

  .counts {
    font-size: var(--fs-xs);
    color: var(--text-3);
  }

  .icon {
    width: 28px;
    height: 28px;
    border-radius: var(--r-sm);
    color: var(--text-2);
    font-size: var(--fs-md);
  }

  .icon:hover {
    background: var(--bg-hover);
  }
</style>
