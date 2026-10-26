<script lang="ts">
  import type { CoOutput } from '../../lib/api';
  import type { CoOutputFull, ParamRow } from './apiDetail';
  import { selectEntry } from '../../lib/stores.svelte';
  import { detailApi } from './apiDetail';
  import { toast } from './toast.svelte';

  let { outputs }: { outputs: CoOutput[] } = $props();

  let showAll = $state(false);

  const full = $derived(outputs as CoOutputFull[]);

  const hasDiff = $derived(full.some((e) => (e.diff_rows ?? []).length > 0));
  const hasRows = $derived(full.some((e) => (e.rows ?? []).length > 0));
  const showToggle = $derived(hasDiff && hasRows);

  function rows(e: CoOutputFull, all: boolean): ParamRow[] {
    return all ? e.rows ?? [] : e.diff_rows ?? [];
  }

  function hashShort(e: CoOutputFull): string {
    return e.state_hash ? e.state_hash.slice(0, 6) : '—';
  }

  async function open(path: string): Promise<void> {
    try {
      await detailApi.openPath(path);
      toast('Opened');
    } catch {
      toast('Failed to open');
    }
  }

  async function reveal(path: string): Promise<void> {
    try {
      await detailApi.revealPath(path);
      toast('Revealed');
    } catch {
      toast('Failed to reveal');
    }
  }
</script>

<div class="dcard-hd">
  <div class="dcard-hd-top">
    <span class="dcard-hd-label">Co-outputs</span>
  </div>
  {#if showToggle}
    <div class="dcard-hd-actions">
      <button class="act-btn" onclick={() => (showAll = !showAll)}>
        {showAll ? 'Show diff only' : 'Show all params'}
      </button>
    </div>
  {/if}
</div>
<div class="dcard-body">
  {#each full as e (e.record_id)}
    <div class="link-row">
      <div class="link-row-top">
        <button class="link-entry-name" onclick={() => selectEntry(e.record_id)}>
          {e.class_name}
        </button>
        <span class="link-hash" title={e.state_hash ?? ''}>{hashShort(e)}</span>
      </div>
      {#if e.primary_file}
        {@const f = e.primary_file}
        <div class="file-row" style="margin-top: 4px">
          <span class="file-name">{f.label}</span>
          <button class="act-btn" onclick={() => open(f.path)}>Open</button>
          <button class="act-btn" onclick={() => reveal(f.path)}>Reveal</button>
        </div>
      {/if}
      {#if rows(e, showAll).length > 0}
        <div class="link-params">
          {#each rows(e, showAll) as r, i (i)}
            <div class="link-param-line">
              <span class="link-param-key">{r.parameter}</span>
              <span class="link-param-val">{r.value}</span>
            </div>
          {/each}
        </div>
      {/if}
    </div>
  {/each}
</div>
