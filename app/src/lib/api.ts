export type ObjectType = 'Data' | 'Figure' | 'Table';

export interface SpecPayload {
  crs: string;
  resolution: string | null;
  resolution_display: string | null;
  shape: string | null;
  bounds: string | null;
  bounds_latlon: string | null;
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
  warning_count?: number;
  warnings?: string[];
  error?: string;
  focused?: boolean;
  source_stale?: boolean;
  dep_hash_stale?: boolean;
  format_version_stale?: boolean;
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

export interface LinkedEntry {
  param_name: string;
  class_name: string;
  state_hash: string;
  params_summary: string;
}

export interface CoOutput {
  class_name: string;
  record_id: string;
  rows: { group: string; parameter: string; value: string }[];
}

export interface SameInstanceRun {
  record_id: string;
  spec: SpecPayload;
}

export interface EntryDetail {
  record_id: string;
  state_hash: string;
  instance_hash: string;
  class_name: string;
  object_type: ObjectType;
  warnings: string[];
  dep_hash_stale: boolean;
  format_version_stale: boolean;
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
  rows: { group: string; parameter: string; value: string; value_type: string; path: string; depth: number }[];
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
  dep_version_siblings?: {
    record_id: string;
    dep_hash: string;
    dep_hash_stale: boolean;
    version_id: string | null;
    version_label: string | null;
    is_self: boolean;
    spec: SpecPayload;
  }[];
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

export interface DashboardPayload {
  selected_classes: string[];
  selected_entry: string | null;
  class_cards: ClassCard[];
  table_rows: TableRow[];
  detail: DetailPayload | null;
  diagnostics: Record<string, unknown>;
  spec_options: Record<string, string[]>;
  version_options: VersionOption[];
  counts: {
    classes: number;
    classes_loaded: number;
    entries: number;
    visible_classes: number;
    visible_entries: number;
  };
  visible_entry_ids: string[];
}

export interface StatusPayload {
  ready: boolean;
  progress: { done?: number; total?: number };
  load_error: string | null;
  has_live_classes: boolean;
  fast: boolean;
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

export interface DashboardRequest {
  selected_classes?: string[];
  selected_entry?: string | null;
  kind_filter?: string;
  spec_filters?: Record<string, string[]>;
  filters?: { target: string; operator: string; value: string }[];
  logic_mode?: 'AND' | 'OR' | 'NOT';
  row_display?: 'none' | 'all' | 'selected';
  hide_stale?: boolean;
  version_filter?: string | null;
}

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
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${url}`);
  return res.json() as Promise<T>;
}

export const api = {
  status: () => getJson<StatusPayload>('/api/status'),
  bootstrap: () => getJson<BootstrapRow[]>('/api/bootstrap'),

  dashboard(body: DashboardRequest = {}): Promise<DashboardPayload> {
    return fetch('/api/dashboard', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then((res) => {
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      return res.json() as Promise<DashboardPayload>;
    });
  },

  popupJson: (path: string) =>
    getJson<Record<string, unknown>>(`/api/popup/json?path=${encodeURIComponent(path)}`),

  fileUrl: (path: string) => `/api/file?path=${encodeURIComponent(path)}`,
  boundsMapUrl: (crs: string) => `/api/bounds-map?crs=${encodeURIComponent(crs)}`,

  rebuild: (reimport: boolean) =>
    postJSON('/api/rebuild', { reimport }),

  cleanCache: (dryRun: boolean) => postJSON<{ lines: string[]; dry_run: boolean }>('/api/clean-cache', { dry_run: dryRun }),

  cleanSource: (dryRun: boolean) =>
    postJSON<{ lines: string[]; dry_run: boolean }>('/api/clean-source', { dry_run: dryRun }),

  deleteEntry: (recordId: string) =>
    fetch(`/api/entry/${encodeURIComponent(recordId)}`, { method: 'DELETE' }).then(async (res) => {
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      return res.json();
    }),
};
