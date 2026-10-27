<script lang="ts">
  import L from 'leaflet';
  import 'leaflet/dist/leaflet.css';
  import { onMount } from 'svelte';

  /** Lat/lon bounds of an entry's spec: [lat_min, lon_min, lat_max, lon_max]. */
  let { bounds, crs }: { bounds: [number, number, number, number]; crs: string } = $props();

  let mapEl: HTMLDivElement;

  const fmt = (lat: number, lon: number) =>
    `${Math.abs(lat)}° ${lat >= 0 ? 'N' : 'S'}, ${Math.abs(lon)}° ${lon >= 0 ? 'E' : 'W'}`;
  const label = $derived(`${fmt(bounds[0], bounds[1])} → ${fmt(bounds[2], bounds[3])}`);

  onMount(() => {
    const [latMin, lonMin, latMax, lonMax] = bounds;
    const box = L.latLngBounds([latMin, lonMin], [latMax, lonMax]);
    const map = L.map(mapEl);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '© OpenStreetMap contributors',
      maxZoom: 18,
    }).addTo(map);
    const accent = getComputedStyle(mapEl).getPropertyValue('--accent').trim() || '#0b6668';
    L.rectangle(box, { color: accent, weight: 2, fillOpacity: 0.15 }).addTo(map);
    map.fitBounds(box, { padding: [30, 30] });
    // The modal may still be settling its size on the first frame.
    const frame = requestAnimationFrame(() => {
      map.invalidateSize();
      map.fitBounds(box, { padding: [30, 30] });
    });
    return () => {
      cancelAnimationFrame(frame);
      map.remove();
    };
  });
</script>

<div class="bounds-map">
  <div class="bounds-map-canvas" bind:this={mapEl}></div>
  <div class="bounds-map-info">{crs ? `${label} · ${crs}` : label}</div>
</div>

<style>
  .bounds-map {
    display: flex;
    flex-direction: column;
    height: 74vh;
  }
  .bounds-map-canvas {
    flex: 1;
    min-height: 0;
  }
  .bounds-map-info {
    padding: 6px 10px;
    font-family: var(--mono);
    font-size: 11px;
    color: var(--muted);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
</style>
