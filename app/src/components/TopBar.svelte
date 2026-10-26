<script lang="ts">
  import {
    filterState,
    layout,
    selection,
    setEntriesMode,
    setKindFilter,
    setParamDisplay,
    setView,
    toggleHideStale,
    toggleSelectMode,
    ui,
  } from '../lib/stores.svelte';
  import type { KindFilter, View } from '../lib/stores.svelte';
  import { codeUi, setBrowseMode, setHideEmpty } from '../lib/nav.svelte';
  import type { CodeKind } from '../lib/nav.svelte';
  import { openModal } from '../lib/modal.svelte';
  import Menu from './Menu.svelte';

  const views: { key: View; label: string }[] = [
    { key: 'entries', label: 'Entries' },
    { key: 'code', label: 'Code' },
    { key: 'export', label: 'Export' },
  ];

  const kinds: { key: KindFilter; label: string }[] = [
    { key: 'all', label: 'All' },
    { key: 'data', label: 'Data' },
    { key: 'table', label: 'Table' },
    { key: 'figure', label: 'Figure' },
  ];

  const codeKinds: { key: CodeKind; label: string }[] = [...kinds, { key: 'trackedobject', label: 'Object' }];

  const exportCount = $derived(selection.selectedEntries.length);
</script>

<nav class="topbar">
  <div class="topbar-left">
    <div class="view-tabs">
      {#each views as v (v.key)}
        <button class="view-tab" class:active={ui.view === v.key} onclick={() => setView(v.key)}>
          {v.label}
          {#if v.key === 'export' && exportCount > 0}<span class="tab-badge">{exportCount}</span>{/if}
        </button>
      {/each}
    </div>
    <div class="topbar-sep"></div>
    {#if ui.view === 'entries'}
      <div class="topbar-toolbar-section">
        <div class="kind-group">
          {#each kinds as k (k.key)}
            <button class="kind-tab" class:active={filterState.kindFilter === k.key} onclick={() => void setKindFilter(k.key)}>
              {k.label}
            </button>
          {/each}
        </div>
      </div>
    {:else if ui.view === 'code'}
      <div class="topbar-toolbar-section">
        <div class="kind-group">
          <button class="kind-tab" class:active={codeUi.browseMode === 'version'} onclick={() => setBrowseMode('version')}>
            By version
          </button>
          <button class="kind-tab" class:active={codeUi.browseMode === 'class'} onclick={() => setBrowseMode('class')}>
            By class
          </button>
        </div>
        <div class="kind-group">
          {#each codeKinds as k (k.key)}
            <button class="kind-tab" class:active={codeUi.kindFilter === k.key} onclick={() => (codeUi.kindFilter = k.key)}>
              {k.label}
            </button>
          {/each}
        </div>
      </div>
    {/if}
  </div>
  <div class="topbar-right">
    {#if ui.view === 'entries'}
      <div class="topbar-toolbar-section">
        <div class="kind-group">
          <button class="kind-tab" class:active={layout.entriesMode === 'compact'} onclick={() => void setEntriesMode('compact')}>
            Compact
          </button>
          <button class="kind-tab" class:active={layout.entriesMode === 'detailed'} onclick={() => void setEntriesMode('detailed')}>
            Detailed
          </button>
        </div>
        <div class="kind-group" class:seg-disabled={layout.entriesMode === 'compact'}>
          <button
            class="kind-tab"
            class:active={filterState.paramDisplay === 'selected'}
            title="Only parameter rows matching the active filters"
            onclick={() => void setParamDisplay('selected')}
          >
            Selected params
          </button>
          <button class="kind-tab" class:active={filterState.paramDisplay === 'all'} onclick={() => void setParamDisplay('all')}>
            All params
          </button>
        </div>
        <div class="kind-group">
          <button class="kind-tab" class:active={filterState.hideStale} onclick={() => void toggleHideStale()}>Hide stale</button>
        </div>
        <div class="kind-group">
          <button class="kind-tab" class:active={selection.selectMode} title="Toggle entry selection for export" onclick={toggleSelectMode}>
            Select
          </button>
        </div>
      </div>
    {:else if ui.view === 'code'}
      <div class="topbar-toolbar-section">
        <div class="kind-group">
          <button class="kind-tab" class:active={codeUi.hideEmpty} onclick={() => setHideEmpty(!codeUi.hideEmpty)}>Hide empty</button>
        </div>
      </div>
    {/if}
    <button class="ghost-btn topbar-icon-btn btn-diag" title="Diagnostics" onclick={() => openModal('Registry diagnostics', { kind: 'diagnostics' }, 'sm')}>
      ⓘ
    </button>
    <Menu />
  </div>
</nav>
