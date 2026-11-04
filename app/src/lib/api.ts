export type ObjectType = 'Data' | 'Figure' | 'Table';

export interface SpecPayload {
  crs: string;
  resolution: string | null;
  resolution_display: string | null;
  shape: string | null;
  bounds: string | null;
  /** [lat_min, lon_min, lat_max, lon_max] */
  bounds_latlon: [number, number, number, number] | null;
  bounds_display: string | null;
}

export interface ClassCard {
  class_name: string;
  object_type: ObjectType;
  loaded: boolean;
  call_dependency_names: string[];
  inheritance_dependency_names: string[];
  total_record_count: number;
  visible_record_count: number;
  selected: boolean;
  source_stale: boolean;
  deps_stale: boolean;
  format_version_stale: boolean;
}

export interface TableRow {
  row_type: 'header' | 'detail';
  class_name: string;
  record_id: string;
  object_type?: ObjectType;
  spec?: SpecPayload;
  focused?: boolean;
  source_stale?: boolean;
  dep_hash_stale?: boolean;
  format_version_stale?: boolean;
  /** The unavailable cache root this entry belongs to; its files can't be checked. */
  offline_root?: string | null;
  dep_hash?: string;
  group?: string;
  parameter?: string;
  value?: string;
  value_type?: string;
  param_row_type?: string;
  path?: string;
  depth?: number;
}

export interface FilePayload {
  label: string;
  path: string;
  kind: string;
}

export interface ParamRow {
  group: string;
  parameter: string;
  value: string;
  value_type?: string;
  param_row_type?: string;
  path?: string;
  depth?: number;
}

export interface FoundEntry {
  record_id: string;
  class_name: string;
  object_type: string | null;
}

export interface LinkedEntry {
  param_name: string;
  class_name: string;
  state_hash: string | null;
  /** List params use a `name[]` key with every item's value. */
  params_summary: Record<string, string[]>;
}

export interface CoOutput {
  record_id: string;
  class_name: string;
  object_type?: string;
  state_hash: string | null;
  offline: boolean;
  primary_file: FilePayload | null;
  rows: ParamRow[];
  diff_rows: ParamRow[];
}

export interface SameInstanceRun {
  record_id: string;
  class_name: string;
  state_hash: string | null;
  offline: boolean;
  primary_file: FilePayload | null;
  spec: SpecPayload;
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

export interface EntryDetail {
  record_id: string;
  state_hash: string;
  instance_hash: string;
  class_name: string;
  object_type: ObjectType;
  dep_hash_stale: boolean;
  format_version_stale: boolean;
  offline_root: string | null;
  dep_hash: string;
  params_path: string;
  state_hash_path: string;
  execution_graph_path: string;
  spec: SpecPayload;
  primary_file: FilePayload | null;
  sidecar_files: FilePayload[];
  figure_preview: string | null;
  table_preview: string | null;
  co_outputs: CoOutput[];
  same_instance_runs: SameInstanceRun[];
  rows: ParamRow[];
  params_tree: Record<string, unknown>;
  linked_entries: LinkedEntry[];
}

export interface DetailPayload {
  class_name: string;
  object_type: ObjectType;
  loaded: boolean;
  call_dependency_names: string[];
  inheritance_dependency_names: string[];
  source_available: boolean;
  graph_available: boolean;
  class_source_path: string | null;
  class_graph_path: string | null;
  class_registry_path: string | null;
  class_tree_path: string | null;
  source_stale: boolean;
  deps_stale: boolean;
  code_versions: { source_hash: string; mtime: string; is_version_change: boolean }[];
  entry_version_id: string | null;
  entry_version_label: string | null;
  dep_version_siblings?: DepVersionSibling[];
  selected_entry: EntryDetail | null;
}

export interface VersionOption {
  version_id: string;
  mtime: string;
  label: string;
  class_names: string[];
  changed_class_names: string[];
  has_entries: boolean;
}

export interface StatusPayload {
  ready: boolean;
  load_error: string | null;
  version: number;
  has_live_classes: boolean;
  mode: 'static' | 'import';
  // epoch seconds; set in import mode while code changed since the last import
  code_changed_since: number | null;
  next_import_at: number | null;
  fast: boolean;
}

export interface UnavailableRoot {
  path: string;
  name: string;
  entries: number;
  /** epoch seconds: when this server process first saw the root unavailable */
  since: number;
}

export interface CatalogInfo {
  mode: 'mirror' | 'writable';
  read_only: boolean;
  reason: string;
  catalog_id: string;
  writer: { root: string; host: string; written_at: number; pygeodata: string; python: string };
  pins_path: string;
  thumbs_path: string;
  absolute_dir_entries: number;
  unavailable_roots: UnavailableRoot[];
}

export interface Diagnostics {
  entries: number;
  created_entries: number;
  unindexed_dirs: number;
  /** why the dirs are not indexed; null when unknown (a read-only mirror never reads them) */
  unindexed_reasons: { other_format: number; no_meta: number; unreadable: number } | null;
  missing_dirs: number;
  offline_entries: number;
  stale_hidden: number;
  /** static analysis problems */
  problems: string[];
}

export interface ClassesPayload {
  class_cards: ClassCard[];
  spec_options: Record<string, (string | { value: string; label: string })[]>;
  version_options: VersionOption[];
  diagnostics: Diagnostics;
  catalog: CatalogInfo;
  counts: {
    classes: number;
    classes_loaded: number;
    entries: number;
    visible_classes: number;
    visible_entries: number;
  };
}

export interface EntriesPagePayload {
  table_rows: TableRow[];
  total: number;
  offset: number;
  limit: number;
}

export interface BootstrapRow {
  state_hash: string;
  class_name: string;
  object_type: string | null;
  source_hash: string | null;
  dependency_tree_hash: string | null;
  instance_hash: string | null;
  params_hash: string | null;
  spec_hash: string | null;
  created_at: number | null;
}

/**
 * GET that bypasses the HTTP cache. The API sends ETags, and Safari can hand a
 * bodiless 304 to fetch() when it revalidates; the app keeps its own caches.
 */
export const fetchFresh = (url: string) => fetch(url, { cache: 'no-store' });

async function postJSON<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

async function getJson<T>(url: string): Promise<T> {
  const res = await fetchFresh(url);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${url}`);
  return res.json() as Promise<T>;
}

export const api = {
  status: () => getJson<StatusPayload>('/api/status'),
  bootstrap: () => getJson<BootstrapRow[]>('/api/bootstrap'),

  classes(params: Record<string, string> = {}): Promise<ClassesPayload> {
    const q = new URLSearchParams(params);
    return getJson<ClassesPayload>(`/api/classes?${q.toString()}`);
  },

  classEntries(params: Record<string, string> = {}): Promise<EntriesPagePayload> {
    const q = new URLSearchParams(params);
    return getJson<EntriesPagePayload>(`/api/class-entries?${q.toString()}`);
  },

  pins: () => getJson<{ pins: FoundEntry[] }>('/api/pins'),

  async setPinned(recordId: string, pinned: boolean): Promise<FoundEntry[]> {
    const res = await fetch(`/api/pins/${encodeURIComponent(recordId)}`, { method: pinned ? 'PUT' : 'DELETE' });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return ((await res.json()) as { pins: FoundEntry[] }).pins;
  },

  findEntries: (prefix: string) =>
    getJson<{ entries: FoundEntry[] }>(`/api/find-entries?q=${encodeURIComponent(prefix)}`),

  entryDetail(recordId: string): Promise<DetailPayload> {
    return getJson<DetailPayload>(`/api/entry/${encodeURIComponent(recordId)}`);
  },

  thumbUrl: (recordId: string, width = 720) => `/api/thumb/${encodeURIComponent(recordId)}?w=${width}`,

  popupJson: (path: string) =>
    getJson<{ title: string; json: unknown }>(`/api/popup/json?path=${encodeURIComponent(path)}`),

  popupGraph: (className: string, graphPath: string | null) =>
    getJson<{ title: string; svg?: string; pdf_path?: string }>(
      `/api/popup/graph?class_name=${encodeURIComponent(className)}` +
        (graphPath ? `&graph_path=${encodeURIComponent(graphPath)}` : ''),
    ),

  fileUrl: (path: string) => `/api/file?path=${encodeURIComponent(path)}`,

  openPath: (path: string) => postJSON('/api/open', { path }),
  revealPath: (path: string) => postJSON('/api/reveal', { path }),

  rebuild: () => postJSON('/api/rebuild', {}),

  cleanCache: (dryRun: boolean) => postJSON<{ lines: string[]; dry_run: boolean }>('/api/clean-cache', { dry_run: dryRun }),

  cleanSource: (dryRun: boolean) =>
    postJSON<{ lines: string[]; dry_run: boolean }>('/api/clean-source', { dry_run: dryRun }),

  deleteEntry: (recordId: string) =>
    fetch(`/api/entry/${encodeURIComponent(recordId)}`, { method: 'DELETE' }).then(async (res) => {
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      return res.json();
    }),
};
