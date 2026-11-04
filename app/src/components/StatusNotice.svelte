<script lang="ts">
  import { startReload, ui } from '../lib/stores.svelte';

  const clock = (epochSeconds: number) =>
    new Date(epochSeconds * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  const pendingImport = $derived(ui.mode === 'import' && ui.codeChangedSince !== null);
  const failure = $derived(ui.ready ? ui.loadError : null);
</script>

{#if failure || pendingImport}
  <div class="status-notice-stack">
    {#if failure}
      <div class="status-notice status-notice--error" role="alert">
        <div>Reload failed — showing the last good state</div>
        <pre>{failure}</pre>
        <button class="act-btn" onclick={() => void startReload()}>Reload now</button>
      </div>
    {/if}
    {#if pendingImport}
      <div class="status-notice">
        <span>
          Code changed since the last import{ui.nextImportAt ? ` — next import at ${clock(ui.nextImportAt)}` : ''}
        </span>
        <button class="act-btn" onclick={() => void startReload()}>Reload now</button>
      </div>
    {/if}
  </div>
{/if}

<style>
  .status-notice-stack {
    position: fixed;
    left: 50%;
    bottom: 14px;
    transform: translateX(-50%);
    display: flex;
    flex-direction: column;
    gap: 8px;
    max-width: min(640px, calc(100vw - 28px));
    z-index: 55;
  }
  .status-notice {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 10px;
    padding: 8px 12px;
    font-size: 12px;
    color: var(--warn);
    background: var(--warn-bg);
    border: 1px solid var(--warn-border);
    border-radius: 10px;
    box-shadow: 0 4px 24px var(--shadow-color);
  }
  .status-notice--error {
    color: var(--danger);
    background: var(--danger-bg);
    border-color: var(--danger-border);
  }
  .status-notice pre {
    flex-basis: 100%;
    margin: 0;
    max-height: 160px;
    overflow: auto;
    font-size: 11px;
    white-space: pre-wrap;
  }
</style>
