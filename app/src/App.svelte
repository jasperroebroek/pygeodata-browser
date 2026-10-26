<script lang="ts">
  import {
    init,
    layout,
    navigateBack,
    navigateForward,
    selectAdjacentEntry,
    selection,
    setDetailWidth,
    ui,
  } from './lib/stores.svelte';
  import { toasts } from './lib/toast.svelte';
  import TopBar from './components/TopBar.svelte';
  import Sidebar from './components/Sidebar.svelte';
  import MainPane from './components/MainPane.svelte';
  import DetailPane from './components/DetailPane.svelte';
  import Modal from './components/Modal.svelte';
  import CodeView from './views/CodeView.svelte';
  import ExportView from './views/ExportView.svelte';

  init();

  const progressPct = $derived.by(() => {
    const p = ui.progress;
    const total = (p.reimport_total ?? 0) + (p.total ?? 0);
    return total ? Math.round((((p.reimport_done ?? 0) + (p.done ?? 0)) / total) * 100) : 0;
  });

  const overlayText = $derived.by(() => {
    const p = ui.progress;
    const rTotal = p.reimport_total ?? 0;
    const rDone = p.reimport_done ?? 0;
    if (rTotal > 0 && rDone < rTotal) {
      return { label: 'Reimporting…', sub: `${rDone} / ${rTotal} files`, pct: Math.round((rDone / rTotal) * 100) };
    }
    if (p.total) {
      return { label: 'Loading entries…', sub: `${p.done ?? 0} / ${p.total}`, pct: Math.round(((p.done ?? 0) / p.total) * 100) };
    }
    if (rTotal > 0) return { label: 'Reimporting…', sub: 'Done — scanning entries…', pct: 100 };
    return { label: ui.reimporting ? 'Reimporting…' : 'Loading entries…', sub: '', pct: 0 };
  });

  // Select mode is always on in the export view (its +/− icons remove entries).
  $effect(() => {
    document.body.classList.toggle('select-mode', selection.selectMode || ui.view === 'export');
  });

  function onKeydown(e: KeyboardEvent) {
    const target = e.target as HTMLElement;
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
    if (ui.view !== 'entries' || (e.key !== 'ArrowDown' && e.key !== 'ArrowUp')) return;
    e.preventDefault();
    void selectAdjacentEntry(e.key === 'ArrowDown' ? 1 : -1);
  }

  // ------------------------------------------------------------------ detail pane resize

  let detailEl: HTMLElement | undefined = $state();
  let dragging = $state(false);
  let startX = 0;
  let startW = 0;
  let dragW = $state<number | null>(null);

  function startResize(e: MouseEvent) {
    if (!detailEl) return;
    e.preventDefault();
    startX = e.clientX;
    startW = detailEl.getBoundingClientRect().width;
    dragging = true;
  }

  function onMouseMove(e: MouseEvent) {
    if (!dragging) return;
    // Drag left = wider.
    dragW = Math.max(200, Math.min(window.innerWidth * 0.8, startW + startX - e.clientX));
  }

  function onMouseUp() {
    if (!dragging) return;
    dragging = false;
    if (dragW !== null) setDetailWidth(dragW);
    dragW = null;
  }

  const detailWidth = $derived(dragW ?? layout.detailWidth);

  $effect(() => {
    document.body.style.cursor = dragging ? 'col-resize' : '';
    document.body.style.userSelect = dragging ? 'none' : '';
  });
</script>

<svelte:window onkeydown={onKeydown} onmousemove={onMouseMove} onmouseup={onMouseUp} />

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
      <!-- svelte-ignore a11y_no_noninteractive_element_interactions (mouse-only drag handle) -->
      <div
        class="resize-handle"
        class:dragging
        role="separator"
        aria-orientation="vertical"
        aria-label="Resize detail pane"
        onmousedown={startResize}
      ></div>
      <aside class="detail-pane" bind:this={detailEl} style:flex={detailWidth ? `0 0 ${detailWidth}px` : null}>
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

{#if (ui.loading && ui.statusKnown && !ui.overlay) || ui.reconciling}
  <div class="fast-progress" title={ui.reimporting ? 'Reimporting Python files…' : 'Loading entries…'}>
    <div class="loading-bar-track fast-progress-track">
      <div class="loading-bar-fill" style:width="{ui.reconciling && !ui.loading ? 100 : progressPct}%"></div>
    </div>
  </div>
{/if}

{#if ui.loading && ui.overlay}
  <div class="loading-overlay">
    <div class="loading-box">
      <div class="loading-label">{overlayText.label}</div>
      <div class="loading-bar-track"><div class="loading-bar-fill" style:width="{overlayText.pct}%"></div></div>
      <div class="loading-sub">{ui.loadError ?? overlayText.sub}</div>
    </div>
  </div>
{/if}

<div class="toast-stack">
  {#each toasts as t (t.id)}
    <div class="toast-item" class:on={t.on}>{t.message}</div>
  {/each}
</div>
