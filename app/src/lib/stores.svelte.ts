import { api } from './api';
import type { BootstrapRow, DashboardPayload, DashboardRequest, StatusPayload } from './api';

export type View = 'entries' | 'code' | 'export';
export type KindFilter = 'all' | 'Data' | 'Table' | 'Figure';
export type LogicMode = 'AND' | 'OR' | 'NOT';

export interface FilterRow {
  target: string;
  operator: string;
  value: string;
}

export interface CodeTarget {
  className: string;
  sourceHash?: string;
}

export const app = $state({
  view: 'entries' as View,
  theme: (localStorage.getItem('pgb-theme') ?? 'system') as 'light' | 'dark' | 'system',

  ready: false,
  loading: true,
  loadError: null as string | null,
  fast: false,

  bootstrap: [] as BootstrapRow[],
  payload: null as DashboardPayload | null,

  selectedClasses: [] as string[],
  selectedEntry: null as string | null,
  kindFilter: 'all' as KindFilter,
  rowDisplay: 'none' as 'none' | 'all',
  classSearch: '',

  filters: [] as FilterRow[],
  logicMode: 'AND' as LogicMode,
  specFilters: {} as Record<string, string[]>,
  versionFilter: null as string | null,
  hideStale: false,
  showEmpty: false,

  selectMode: false,
  selectedEntries: [] as string[],

  codeTarget: null as CodeTarget | null,
  diffRecordId: null as string | null,
});

let statusTimer: ReturnType<typeof setInterval> | null = null;

export function applyTheme() {
  const el = document.documentElement;
  if (app.theme === 'system') {
    el.removeAttribute('data-theme');
  } else {
    el.dataset.theme = app.theme;
  }
  localStorage.setItem('pgb-theme', app.theme);
}

export function toggleTheme() {
  const resolved = matchMedia('(prefers-color-scheme: dark)').matches ? 'light' : 'dark';
  app.theme = app.theme === 'system' ? resolved : app.theme === 'dark' ? 'light' : 'dark';
  applyTheme();
}

let refreshSeq = 0;

export async function refreshDashboard() {
  const seq = ++refreshSeq;
  const body: DashboardRequest = {
    selected_classes: app.selectedClasses,
    selected_entry: app.selectedEntry,
    kind_filter: app.kindFilter,
    row_display: app.rowDisplay,
    filters: app.filters,
    logic_mode: app.logicMode,
    spec_filters: app.specFilters,
    hide_stale: app.hideStale,
    version_filter: app.versionFilter,
  };
  for (let attempt = 0; attempt < 60; attempt++) {
    const res = await fetch('/api/dashboard', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    // 202 = still loading: keep the last payload on screen instead of a stub
    if (res.status === 202) {
      await new Promise((r) => setTimeout(r, 500));
      continue;
    }
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    const payload = (await res.json()) as DashboardPayload;
    if (seq === refreshSeq) app.payload = payload;
    return payload;
  }
  return app.payload;
}

export async function selectClasses(classes: string[], opts: { autoOpen?: boolean } = {}) {
  app.selectedClasses = classes;
  // Explicit requirement: clicking a class auto-opens its first table row.
  if (opts.autoOpen !== false && classes.length > 0) {
    const payload = await refreshDashboard();
    const firstHeader = payload?.table_rows.find((r) => r.row_type === 'header');
    app.selectedEntry = firstHeader?.record_id ?? null;
  } else {
    app.selectedEntry = null;
  }
  await refreshDashboard();
}

export async function selectEntry(recordId: string | null) {
  app.selectedEntry = recordId;
  await refreshDashboard();
}

export async function setKindFilter(kind: KindFilter) {
  app.kindFilter = kind;
  await refreshDashboard();
}

export async function setRowDisplay(mode: 'none' | 'all') {
  app.rowDisplay = mode;
  await refreshDashboard();
}

export async function setLogicMode(mode: LogicMode) {
  app.logicMode = mode;
  await refreshDashboard();
}

export async function setFilters(filters: FilterRow[]) {
  app.filters = filters;
  await refreshDashboard();
}

export async function toggleSpecFilter(dimension: string, value: string) {
  const current = app.specFilters[dimension] ?? [];
  const next = current.includes(value) ? current.filter((v) => v !== value) : [...current, value];
  const nextFilters = { ...app.specFilters, [dimension]: next };
  if (next.length === 0) delete nextFilters[dimension];
  app.specFilters = nextFilters;
  await refreshDashboard();
}

export async function setVersionFilter(versionId: string | null) {
  app.versionFilter = versionId;
  await refreshDashboard();
}

export async function toggleHideStale() {
  app.hideStale = !app.hideStale;
  await refreshDashboard();
}

export function toggleShowEmpty() {
  app.showEmpty = !app.showEmpty;
}

export function setSelectMode(on: boolean) {
  app.selectMode = on;
  if (!on) app.selectedEntries = [];
}

export function toggleSelectedEntry(recordId: string) {
  app.selectedEntries = app.selectedEntries.includes(recordId)
    ? app.selectedEntries.filter((id) => id !== recordId)
    : [...app.selectedEntries, recordId];
}

export function setSelectedEntries(ids: string[]) {
  app.selectedEntries = ids;
}

export async function startReload(reimport = false) {
  app.loading = true;
  app.ready = false;
  try {
    const res = await fetch('/api/rebuild', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reimport }),
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  } catch (err) {
    app.loading = false;
    console.error('reload failed', err);
    return;
  }
  pollStatus();
}

// kept for compatibility with earlier components
export const reloadState = () => startReload(false);

async function onReady() {
  app.loading = false;
  app.ready = true;
  if (app.bootstrap.length > 0) {
    // Fast mode: bootstrap already painted the class list; the full state swaps in.
    app.bootstrap = [];
  }
  await refreshDashboard();
}

export function pollStatus() {
  if (statusTimer) clearInterval(statusTimer);
  const check = async () => {
    try {
      const status: StatusPayload = await api.status();
      app.fast = status.fast;
      app.loadError = status.load_error;
      if (status.ready) {
        if (statusTimer) clearInterval(statusTimer);
        statusTimer = null;
        await onReady();
      }
    } catch {
      /* backend briefly unreachable during dev reloads */
    }
  };
  check();
  if (!app.ready) statusTimer = setInterval(check, 500);
}

export async function init() {
  applyTheme();
  try {
    app.bootstrap = await api.bootstrap();
  } catch {
    app.bootstrap = [];
  }
  pollStatus();
}
