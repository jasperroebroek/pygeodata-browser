<script lang="ts">
  import type { SpecPayload } from '../../lib/api';

  let {
    spec,
    onBoundsMap = null,
  }: {
    spec: SpecPayload;
    onBoundsMap?: ((spec: SpecPayload) => void) | null;
  } = $props();

  const crsMatch = $derived(spec.crs?.match(/^(?:EPSG|ESRI):(\d+)$/));
  const epsgUrl = $derived(crsMatch ? `https://epsg.io/${crsMatch[1]}` : null);
</script>

<div class="spec-kv-table">
  {#if spec.crs}
    <div class="spec-kv-row">
      <span class="spec-kv-label">CRS</span>
      <span class="spec-kv-val">
        {#if epsgUrl}
          <a href={epsgUrl} target="_blank" rel="noopener">{spec.crs}</a>
        {:else}
          {spec.crs}
        {/if}
      </span>
    </div>
  {/if}
  {#if spec.resolution_display}
    <div class="spec-kv-row">
      <span class="spec-kv-label">Resolution</span>
      <span class="spec-kv-val">{spec.resolution_display}</span>
    </div>
  {/if}
  {#if spec.shape}
    <div class="spec-kv-row">
      <span class="spec-kv-label">Shape</span>
      <span class="spec-kv-val">{spec.shape}</span>
    </div>
  {/if}
  {#if spec.bounds_display}
    <div class="spec-kv-row">
      <span class="spec-kv-label">Bounds</span>
      <span class="spec-kv-val">
        {#if spec.bounds_latlon && onBoundsMap}
          <button class="act-btn" title="Show bounds map" onclick={() => onBoundsMap?.(spec)}>
            {spec.bounds_display}
          </button>
        {:else}
          {spec.bounds_display}
        {/if}
      </span>
    </div>
  {/if}
</div>
