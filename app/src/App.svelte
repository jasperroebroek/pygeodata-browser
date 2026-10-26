<script lang="ts">
  import { app, init, pollStatus } from './lib/stores.svelte';
  import TopBar from './components/TopBar.svelte';
  import ClassColumn from './components/ClassColumn.svelte';
  import TableColumn from './components/TableColumn.svelte';
  import DetailColumn from './components/DetailColumn.svelte';
  import CodeView from './views/CodeView.svelte';
  import ExportView from './views/ExportView.svelte';

  init();
</script>

<div class="shell">
  <TopBar />
  {#if app.loading || app.reconciling}
    <div class="progress-row" data-loading>
      {#if app.bootstrap.length > 0}
        {@const done = (app.progress.done ?? 0) / Math.max(app.progress.total ?? 0, 1)}
        <div class="progress-bar">
          <div class="progress-fill" style={app.progress.total ? `width: ${(done * 100).toFixed(1)}%` : ''} data-has-total={!!app.progress.total}></div>
        </div>
        <span class="progress-label">
          {#if app.reconciling && !app.loading}
            Reconciling…
          {:else if app.progress.total}
            {app.progress.done ?? 0}/{app.progress.total} entries
          {:else}
            Building full state…
          {/if}
        </span>
      {:else}
        <div class="boot-screen">
          <div class="boot-title">Registry</div>
          <div class="progress-bar"><div class="progress-fill" data-indeterminate></div></div>
          {#if app.loadError}
            <pre class="boot-error">{app.loadError}</pre>
          {:else}
            <div class="progress-label">Loading cache state…</div>
          {/if}
        </div>
      {/if}
    </div>
  {/if}
  {#if app.view === 'entries'}
    <main class="columns" class:ready={!app.loading}>
      <ClassColumn />
      <TableColumn />
      <DetailColumn />
    </main>
  {:else if app.view === 'code'}
    <main class="full"><CodeView /></main>
  {:else}
    <main class="full"><ExportView /></main>
  {/if}
</div>

<style>
  .shell {
    display: flex;
    flex-direction: column;
    height: 100%;
  }

  .columns {
    display: grid;
    grid-template-columns: 300px minmax(0, 1fr) minmax(0, 1.2fr);
    flex: 1;
    min-height: 0;
  }

  .columns.ready > :global(*) {
    opacity: 1;
  }

  .columns > :global(*) {
    opacity: 0.45;
    transition: opacity var(--t-med) var(--ease);
  }

  .progress-row {
    height: 3px;
    background: var(--bg-panel);
  }

  .progress-bar {
    height: 100%;
    width: 100%;
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    width: 34%;
    background: var(--accent);
    border-radius: var(--r-full);
  }

  .progress-fill:not([data-has-total='true']) {
    animation: slide 1.1s var(--ease) infinite;
  }

  @keyframes slide {
    from {
      transform: translateX(-110%);
    }
    to {
      transform: translateX(410%);
    }
  }

  .progress-label {
    position: absolute;
    left: 50%;
    transform: translateX(-50%);
    font-size: var(--fs-xs);
    color: var(--text-3);
    margin-top: var(--s-2);
  }

  .progress-row {
    position: relative;
  }

  .boot-screen {
    position: fixed;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--s-3);
    background: var(--bg);
    z-index: 10;
  }

  .boot-title {
    font-size: 1.3rem;
    font-weight: 600;
    letter-spacing: -0.02em;
  }

  .boot-screen .progress-bar {
    height: 3px;
    width: 180px;
  }

  .boot-error {
    max-width: 70ch;
    max-height: 40vh;
    overflow: auto;
    font-family: var(--font-mono);
    font-size: var(--fs-xs);
    color: var(--danger);
    background: var(--code-bg);
    padding: var(--s-3);
    border-radius: var(--r-md);
  }

  .full {
    flex: 1;
    min-height: 0;
    display: flex;
  }
</style>
