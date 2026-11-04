<script lang="ts">
  import {
    init,
    layout,
    navigateBack,
    navigateForward,
    selectAdjacentEntry,
    selection,
    ui,
  } from './lib/stores.svelte';
  import { toasts } from './lib/toast.svelte';
  import TopBar from './components/TopBar.svelte';
  import Sidebar from './components/Sidebar.svelte';
  import MainPane from './components/MainPane.svelte';
  import DetailPane from './components/DetailPane.svelte';
  import Modal from './components/Modal.svelte';
  import QuickSwitcher from './components/QuickSwitcher.svelte';
  import ReloadBar from './components/ReloadBar.svelte';
  import StatusNotice from './components/StatusNotice.svelte';
  import { palette } from './lib/palette.svelte';
  import Resizer from './components/Resizer.svelte';
  import CodeView from './views/CodeView.svelte';
  import ExportView from './views/ExportView.svelte';

  init();

  // Select mode is always on in the export view (its +/− icons remove entries).
  $effect(() => {
    document.body.classList.toggle('select-mode', selection.selectMode || ui.view === 'export');
  });

  function onKeydown(e: KeyboardEvent) {
    const target = e.target as HTMLElement;
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
      e.preventDefault();
      palette.open = !palette.open;
      return;
    }
    if (e.metaKey && e.key === '[') {
      e.preventDefault();
      void navigateBack();
      return;
    }
    if (e.metaKey && e.key === ']') {
      e.preventDefault();
      void navigateForward();
      return;
    }
    if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT') return;
    if (e.key === '/' && ui.view === 'entries') {
      const filter = document.querySelector<HTMLInputElement>('.class-filter');
      if (filter) {
        e.preventDefault();
        filter.focus();
        filter.select();
      }
      return;
    }
    if (ui.view !== 'entries' || (e.key !== 'ArrowDown' && e.key !== 'ArrowUp')) return;
    e.preventDefault();
    void selectAdjacentEntry(e.key === 'ArrowDown' ? 1 : -1);
  }
</script>

<svelte:window onkeydown={onKeydown} />

<TopBar />

{#if ui.view === 'entries'}
  <div class="view-entries">
    <div
      class="app-layout"
      class:mode-compact={layout.entriesMode === 'compact'}
      class:mode-detailed={layout.entriesMode === 'detailed'}
    >
      <Sidebar />
      <MainPane />
      <aside class="detail-pane" style:flex={layout.widths.detail ? `0 0 ${layout.widths.detail}px` : null}>
        <Resizer pane="detail" edge="left" min={280} max={() => window.innerWidth * 0.8} />
        <ReloadBar />
        <DetailPane />
      </aside>
    </div>
  </div>
{:else if ui.view === 'code'}
  <CodeView />
{:else}
  <ExportView />
{/if}

<Modal />

<StatusNotice />

{#if palette.open}<QuickSwitcher />{/if}

{#if ui.loading && ui.overlay}
  <div class="loading-overlay">
    <div class="loading-box"><div class="loading-label">Loading entries…</div></div>
  </div>
{/if}

<div class="toast-stack">
  {#each toasts as t (t.id)}
    <div class="toast-item" class:on={t.on}>{t.message}</div>
  {/each}
</div>
