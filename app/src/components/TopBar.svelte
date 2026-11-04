<script lang="ts">
  import Activity from '@lucide/svelte/icons/activity';
  import List from '@lucide/svelte/icons/list';
  import ListChecks from '@lucide/svelte/icons/list-checks';
  import Pin from '@lucide/svelte/icons/pin';
  import Search from '@lucide/svelte/icons/search';
  import Table2 from '@lucide/svelte/icons/table-2';
  import {
    classesState,
    filterState,
    layout,
    pinsState,
    selection,
    setEntriesMode,
    setKindFilter,
    setOfflineFilter,
    setPinnedOnly,
    toggleSelectMode,
    ui,
  } from '../lib/stores.svelte';
  import type { KindFilter, OfflineFilter, View } from '../lib/stores.svelte';
  import { codeUi, setBrowseMode, switchView } from '../lib/nav.svelte';
  import type { CodeKind } from '../lib/nav.svelte';
  import { openModal } from '../lib/modal.svelte';
  import { palette } from '../lib/palette.svelte';
  import Menu from './Menu.svelte';
  import ViewSettings from './ViewSettings.svelte';

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

  const isMac = navigator.platform.toLowerCase().includes('mac');

  const offlineCount = $derived(classesState.diagnostics.offline_entries ?? 0);

  // Clicking the active tab clears it, as with the pinned toggle.
  const toggleOffline = (filter: Exclude<OfflineFilter, 'all'>) =>
    void setOfflineFilter(filterState.offlineFilter === filter ? 'all' : filter);

  const exportCount = $derived(selection.selectedEntries.length);
</script>

<nav class="topbar">
  <div class="topbar-left">
    <div class="view-tabs">
      {#each views as v (v.key)}
        <button class="view-tab" class:active={ui.view === v.key} onclick={() => switchView(v.key)}>
          <span class="tab-label" data-label={v.label}>{v.label}</span>
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
              <span class="tab-label" data-label={k.label}>{k.label}</span>
            </button>
          {/each}
        </div>
        {#if offlineCount > 0}
          <div class="kind-group">
            <button
              class="kind-tab"
              class:active={filterState.offlineFilter === 'online'}
              title="Hide entries of unavailable cache roots"
              aria-pressed={filterState.offlineFilter === 'online'}
              onclick={() => toggleOffline('online')}
            >
              <span class="tab-label" data-label="Online">Online</span>
            </button>
            <button
              class="kind-tab"
              class:active={filterState.offlineFilter === 'offline'}
              title="Show only entries of unavailable cache roots"
              aria-pressed={filterState.offlineFilter === 'offline'}
              onclick={() => toggleOffline('offline')}
            >
              <span class="tab-label" data-label={`Offline (${offlineCount})`}>Offline ({offlineCount})</span>
            </button>
          </div>
        {/if}
        <div class="kind-group">
          <button
            class="kind-tab kind-tab--pinned"
            class:active={filterState.pinnedOnly}
            title={filterState.pinnedOnly ? 'Show all entries' : 'Show only pinned entries'}
            aria-pressed={filterState.pinnedOnly}
            onclick={() => void setPinnedOnly(!filterState.pinnedOnly)}
          >
            <Pin size={13} fill={filterState.pinnedOnly ? 'currentColor' : 'none'} />
            <span class="tab-label" data-label="Pinned">Pinned</span>
            {#if pinsState.list.length}<span class="tab-badge">{pinsState.list.length}</span>{/if}
          </button>
        </div>
      </div>
    {:else if ui.view === 'code'}
      <div class="topbar-toolbar-section">
        <div class="kind-group">
          <button class="kind-tab" class:active={codeUi.browseMode === 'version'} onclick={() => setBrowseMode('version')}>
            <span class="tab-label" data-label="By version">By version</span>
          </button>
          <button class="kind-tab" class:active={codeUi.browseMode === 'class'} onclick={() => setBrowseMode('class')}>
            <span class="tab-label" data-label="By class">By class</span>
          </button>
        </div>
        <div class="kind-group">
          {#each codeKinds as k (k.key)}
            <button class="kind-tab" class:active={codeUi.kindFilter === k.key} onclick={() => (codeUi.kindFilter = k.key)}>
              <span class="tab-label" data-label={k.label}>{k.label}</span>
            </button>
          {/each}
        </div>
      </div>
    {/if}
  </div>
  <div class="topbar-right">
    <button class="search-btn" title="Quick switcher" onclick={() => (palette.open = true)}>
      <Search size={15} />
      <span>Jump to…</span>
      <kbd>{isMac ? '⌘' : 'Ctrl+'}K</kbd>
    </button>
    {#if ui.view === 'entries'}
      <div class="kind-group">
        <button
          class="kind-tab kind-tab--icon"
          class:active={layout.entriesMode === 'compact'}
          title="Compact list"
          aria-label="Compact"
          onclick={() => void setEntriesMode('compact')}
        >
          <List size={18} />
        </button>
        <button
          class="kind-tab kind-tab--icon"
          class:active={layout.entriesMode === 'detailed'}
          title="Detailed table with parameter rows"
          aria-label="Detailed"
          onclick={() => void setEntriesMode('detailed')}
        >
          <Table2 size={18} />
        </button>
      </div>
      <div class="kind-group">
        <button
          class="kind-tab kind-tab--icon"
          class:active={selection.selectMode}
          title="Select entries for export"
          aria-label="Select"
          onclick={toggleSelectMode}
        >
          <ListChecks size={18} />
        </button>
      </div>
    {/if}
    <div class="topbar-icons">
      <ViewSettings />
      <button class="icon-btn" title="Registry diagnostics" onclick={() => openModal('Registry diagnostics', { kind: 'diagnostics' }, 'md')}>
        <Activity size={20} />
      </button>
      <Menu />
    </div>
  </div>
</nav>
