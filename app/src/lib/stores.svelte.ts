import { api } from './api';
import type { BootstrapRow, DashboardPayload, DashboardRequest, StatusPayload } from './api';

export type View = 'entries' | 'code' | 'export';
export type KindFilter = 'all' | 'Data' | 'Table' | 'Figure';

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

async function refreshDashboard() {
  const body: DashboardRequest = {
    selected_classes: app.selectedClasses,
    selected_entry: app.selectedEntry,
    kind_filter: app.kindFilter,
    row_display: app.rowDisplay,
  };
  try {
    app.payload = await api.dashboard(body);
  } catch (err) {
    console.error('dashboard failed', err);
  }
}

export async function selectClasses(classes: string[], opts: { autoOpen?: boolean } = {}) {
  app.selectedClasses = classes;
  // Explicit requirement: clicking a class auto-opens its first table row.
  if (opts.autoOpen !== false && classes.length > 0) {
    const payload = await api.dashboard({
      selected_classes: classes,
      kind_filter: app.kindFilter,
      row_display: app.rowDisplay,
    });
    app.payload = payload;
    const firstHeader = payload.table_rows.find((r) => r.row_type === 'header');
    app.selectedEntry = firstHeader?.record_id ?? null;
    if (app.selectedEntry) {
      await refreshDashboard();
      return;
    }
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

export async function reloadState() {
  app.loading = true;
  await fetch('/api/rebuild', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
  pollStatus();
}

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
