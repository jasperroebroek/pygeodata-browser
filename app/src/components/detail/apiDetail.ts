import type { SameInstanceRun, SpecPayload } from '../../lib/api';
import { api } from '../../lib/api';

// Keys hidden from the params tree at the root level (legacy detail.js parity).
export const HIDDEN_JSON_KEYS = new Set([
  'class_name',
  'object_type',
  'source_hash',
  'state_hash',
  'dependency_tree_hash',
  'tree',
  'call_dependencies',
  'inheritance_dependencies',
  'dependencies',
  'crs',
  'transform',
]);

// The dashboard's shared types narrow some detail payloads; these capture what
// api/payloads.py actually serialises (co-output rows, sibling file refs, etc.).
export interface ParamRow {
  group: string;
  parameter: string;
  value: string;
  value_type?: string;
  param_row_type?: string;
  path?: string;
  depth?: number;
}

export interface CoOutputFull {
  record_id: string;
  class_name: string;
  object_type?: string;
  state_hash?: string | null;
  primary_file?: { label: string; path: string; kind: string } | null;
  rows: ParamRow[];
  diff_rows?: ParamRow[];
}

export interface SameInstanceRunFull extends SameInstanceRun {
  class_name: string;
  state_hash?: string | null;
  primary_file?: { label: string; path: string; kind: string } | null;
  spec: SpecPayload;
}

export interface LinkedEntryFull {
  param_name: string;
  class_name: string;
  state_hash: string | null;
  params_summary: Record<string, string>;
}

export interface DepVersionSibling {
  record_id: string;
  dep_hash: string;
  dep_hash_stale: boolean;
  version_id: string | null;
  version_label: string | null;
  is_self: boolean;
  spec: SpecPayload;
}

const RASTER_EXTS = new Set(['.tif', '.tiff', '.nc', '.vrt', '.npy', '.zarr']);

export function fileExt(path: string): string {
  const i = path.lastIndexOf('.');
  return i === -1 ? '' : path.slice(i).toLowerCase();
}

export function isRasterFile(path: string): boolean {
  return RASTER_EXTS.has(fileExt(path));
}

async function postOk(url: string, body: Record<string, unknown>): Promise<void> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
}

export const detailApi = {
  openPath: (path: string) => postOk('/api/open', { path }),
  revealPath: (path: string) => postOk('/api/reveal', { path }),

  boundsMapUrl: (bounds: number[], crs: string) =>
    `/api/bounds-map?bounds=${encodeURIComponent(JSON.stringify(bounds))}&crs=${encodeURIComponent(crs)}`,

  async copyText(text: string): Promise<void> {
    await navigator.clipboard.writeText(text);
  },

  async fetchText(url: string): Promise<string> {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.text();
  },
};

/**
 * Wrap a fetched table-preview HTML fragment in a full document for an iframe
 * srcdoc. Styles are derived from the live design tokens so the preview follows
 * the active theme; rem-based tokens are converted to px because the iframe
 * document has its own root font-size.
 */
export function tableSrcdoc(html: string): string {
  const root = getComputedStyle(document.documentElement);
  const v = (name: string) => root.getPropertyValue(name).trim();
  return `<!DOCTYPE html><html><head><meta charset="utf-8"><style>
  body { margin: 0; padding: 10px 12px; font-family: ${v('--font-ui')}; font-size: 13px; color: ${v('--text')}; background: ${v('--bg-elev')}; }
  h2 { font-size: 13px; font-weight: 600; margin: 0 0 8px; }
  table { border-collapse: collapse; border-spacing: 0; border: 1px solid ${v('--border-strong')}; font-size: 12px; width: max-content; min-width: 100%; }
  thead th { position: sticky; top: 0; background: ${v('--bg-hover')}; padding: 3px 8px; border-bottom: 1px solid ${v('--border-strong')}; white-space: nowrap; text-align: left; }
  tbody td, tbody th { padding: 2px 8px; border-bottom: 1px solid ${v('--border')}; white-space: nowrap; text-align: left; font-weight: 400; }
  tbody tr:last-child td, tbody tr:last-child th { border-bottom: none; }
  tbody tr:hover { background: ${v('--bg-hover')}; }
  </style></head><body>${html}</body></html>`;
}

export function formatMtime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(d);
}
