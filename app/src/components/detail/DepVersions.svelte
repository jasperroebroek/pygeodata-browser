<script lang="ts">
  import type { DetailPayload } from '../../lib/api';
  import type { DepVersionSibling } from './apiDetail';
  import { selectEntry } from '../../lib/stores.svelte';

  let { detail }: { detail: DetailPayload } = $props();

  const versions = $derived((detail.dep_version_siblings ?? []) as DepVersionSibling[]);
  const show = $derived(versions.length > 1);

  function specParts(s: DepVersionSibling): string[] {
    return [s.spec?.crs, s.spec?.resolution_display, s.spec?.shape, s.spec?.bounds_display].filter(
      (v): v is string => Boolean(v),
    );
  }
</script>

{#if show}
  <div class="dcard">
    <div class="dcard-hd">
      <span class="dcard-hd-label">Versions</span>
      <span class="dcard-hd-meta">{versions.length}</span>
    </div>
    <div class="dcard-body">
      {#each versions as s (s.record_id)}
        <div class="ver-row" class:ver-row--self={s.is_self}>
          <div class="ver-row-main">
            <span class="ver-label">{s.version_label ?? '—'}</span>
            {#if s.dep_hash_stale}
              <span class="dbadge dbadge--warn" title="Dependencies changed — entry may be outdated">
                stale
              </span>
            {:else}
              <span class="dbadge dbadge--ok">current</span>
            {/if}
            {#if !s.is_self}
              <button class="act-btn ver-select" onclick={() => selectEntry(s.record_id)}>
                Select
              </button>
            {/if}
          </div>
          {#if specParts(s).length > 0}
            <div class="ver-row-spec">
              {#each specParts(s) as part (part)}
                <span class="spec-pill">{part}</span>
              {/each}
            </div>
          {/if}
        </div>
      {/each}
    </div>
  </div>
{/if}
