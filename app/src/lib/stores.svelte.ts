import { api, fetchFresh } from './api';
import { toast } from './toast.svelte';
import type {
  BootstrapRow,
  ClassCard,
  CatalogInfo,
  ClassesPayload,
  DetailPayload,
  EntriesPagePayload,
  FoundEntry,
  StatusPayload,
  TableRow,
  VersionOption,
} from './api';

export type View = 'entries' | 'code' | 'export';
export type KindFilter = 'all' | 'data' | 'table' | 'figure';
export type OfflineFilter = 'all' | 'online' | 'offline';
export type LogicMode = 'AND' | 'OR' | 'NOT';
export type EntriesMode = 'compact' | 'detailed';
export type ParamDisplay = 'selected' | 'all';
export type Theme = 'light' | 'dark' | 'system';

export interface FilterRow {
  target: string;
  operator: string;
  value: string;
}

export interface SpecOption {
  value: string;
  label: string;
}

function stored(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function store(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* private mode: preference is session-only */
  }
}

// ---------------------------------------------------------------------------
// Focused state runes: a detail swap never invalidates the class column, a
// filter change never re-renders the entry table from a foreign payload.
// ---------------------------------------------------------------------------

const savedView = stored('view_mode_top');

export const ui = $state({
  view: (savedView === 'code' || savedView === 'export' ? savedView : 'entries') as View,
  theme: (stored('pgb-theme') ?? 'light') as Theme,
  ready: false,
  loading: true,
  reconciling: false,
  // Blocking overlay: only a non-fast first load (nothing to show yet). Reloads
  // keep the current state on screen behind the slim progress bar.
  overlay: false,
  statusKnown: false,
  loadError: null as string | null,
  fast: false,
  hasLiveClasses: false,
  mode: 'static' as 'static' | 'import',
  codeChangedSince: null as number | null,
  nextImportAt: null as number | null,
  bootstrap: [] as BootstrapRow[],
});

export type PaneKey = 'sidebar' | 'detail' | 'codeVersions' | 'codeClasses';

const PANES: PaneKey[] = ['sidebar', 'detail', 'codeVersions', 'codeClasses'];
const PANE_STORAGE: Record<PaneKey, string> = {
  sidebar: 'registry.sidebar-w',
  detail: 'registry.detail-w',
  codeVersions: 'pgb-pane-code-versions',
  codeClasses: 'pgb-pane-code-classes',
};

export const layout = $state({
  // Detailed on normal/wide screens, compact on narrow ones.
  entriesMode: (window.innerWidth >= 1000 ? 'detailed' : 'compact') as EntriesMode,
  sidebarCollapsed: stored('registry.sidebar-collapsed') === '1',
  // Dragged pane widths; null keeps the stylesheet default.
  widths: Object.fromEntries(
    PANES.map((k) => [k, Number(stored(PANE_STORAGE[k])) || null]),
  ) as Record<PaneKey, number | null>,
});

export const filterState = $state({
  kindFilter: 'all' as KindFilter,
  paramDisplay: 'all' as ParamDisplay,
  logicMode: 'AND' as LogicMode,
  filters: [] as FilterRow[],
  specFilters: {} as Record<string, string[]>,
  versionFilter: null as string | null,
  hideStale: stored('hide_stale') === 'true',
  /** Entries of unavailable cache roots: all, only the online ones, or only the offline ones. */
  offlineFilter: 'all' as OfflineFilter,
  /** Show only pinned entries (across all classes when none is selected). */
  pinnedOnly: false,
});

export const classesState = $state({
  cards: [] as ClassCard[],
  specOptions: {} as Record<string, (string | SpecOption)[]>,
  versionOptions: [] as VersionOption[],
  counts: null as ClassesPayload['counts'] | null,
  diagnostics: {} as Record<string, number>,
  catalog: null as CatalogInfo | null,
});

class TableState {
  selectedClasses = $state<string[]>([]);
  selectedEntry = $state<string | null>(null);
  // Pages are replaced or appended, never mutated: raw keeps thousands of
  // param rows out of deep reactivity.
  rows = $state.raw<TableRow[]>([]);
  total = $state(0);
  loadedCount = $state(0);
  fullyLoaded = $state(false);
  loading = $state(false);
}

export const tableState = new TableState();

export const detailState = $state({
  current: null as DetailPayload | null,
  loading: false,
  /** The focused entry's detail failed to load (shown instead of an empty pane). */
  failed: false,
});

/** Pinned entries (project-wide, stored next to the registry), in pin order. */
export const pinsState = $state({ list: [] as FoundEntry[] });

export const isPinned = (recordId: string) => pinsState.list.some((p) => p.record_id === recordId);

export async function loadPins() {
  try {
    const { pins } = await api.pins();
    if (pins) pinsState.list = pins;
  } catch (err) {
    console.error('pins failed', err);
  }
}

/** Optimistic: the pin shows at once and is rolled back if the server refuses. */
export async function setPinned(entry: FoundEntry, pinned: boolean) {
  const before = pinsState.list;
  pinsState.list = pinned ? [...before.filter((p) => p.record_id !== entry.record_id), entry] : before.filter((p) => p.record_id !== entry.record_id);
  try {
    pinsState.list = await api.setPinned(entry.record_id, pinned);
  } catch {
    pinsState.list = before;
    toast(pinned ? 'Could not pin entry' : 'Could not unpin entry');
    return;
  }
  // Cached pinned-view pages are now out of date.
  firstPageCache.clear();
  if (filterState.pinnedOnly) await loadEntries(0, true);
}

export async function setPinnedOnly(on: boolean) {
  filterState.pinnedOnly = on;
  await loadEntries(0, true);
  const first = tableState.rows.find((r) => r.row_type === 'header');
  if (on && first && !tableState.rows.some((r) => r.record_id === tableState.selectedEntry)) {
    await selectEntry(first.record_id);
  }
}

export const selection = $state({
  selectMode: false,
  selectedEntries: [] as string[],
  showEmpty: false,
  multiClass: false,
});

// Entry details are immutable (content-addressed by state_hash): cache in the
// session, never refetch. Cleared on rebuild, since staleness badges change.
const detailCache = new Map<string, DetailPayload>();
const detailInflight = new Map<string, Promise<DetailPayload>>();

// First entry pages by URL (the URL carries every filter). State only changes on
// rebuild, so they stay valid until then; this makes revisits and hover prefetch instant.
const firstPageCache = new Map<string, Promise<EntriesPagePayload>>();
const FIRST_PAGE_CACHE_SIZE = 24;

function clearCaches() {
  detailCache.clear();
  detailInflight.clear();
  firstPageCache.clear();
}

export function rowDisplay(): 'none' | ParamDisplay {
  return layout.entriesMode === 'compact' ? 'none' : filterState.paramDisplay;
}

// ---------------------------------------------------------------------------
// Theme / layout preferences
// ---------------------------------------------------------------------------

const darkQuery = matchMedia('(prefers-color-scheme: dark)');

export function applyTheme() {
  const resolved = ui.theme === 'system' ? (darkQuery.matches ? 'dark' : 'light') : ui.theme;
  document.documentElement.dataset.theme = resolved;
  store('pgb-theme', ui.theme);
}

darkQuery.addEventListener('change', () => {
  if (ui.theme === 'system') applyTheme();
});

export function setTheme(theme: Theme) {
  ui.theme = theme;
  applyTheme();
}

export function setView(view: View) {
  ui.view = view;
  store('view_mode_top', view);
}

export function setSidebarCollapsed(collapsed: boolean) {
  layout.sidebarCollapsed = collapsed;
  store('registry.sidebar-collapsed', collapsed ? '1' : '0');
}

/** Persist a dragged pane width; null resets it to the stylesheet default. */
export function setPaneWidth(pane: PaneKey, px: number | null) {
  layout.widths[pane] = px === null ? null : Math.round(px);
  try {
    if (px === null) localStorage.removeItem(PANE_STORAGE[pane]);
    else localStorage.setItem(PANE_STORAGE[pane], String(layout.widths[pane]));
  } catch {
    /* private mode: preference is session-only */
  }
}

// ---------------------------------------------------------------------------
// Fetch helpers with reconcile (202) retry
// ---------------------------------------------------------------------------

async function getRetry<T>(url: string): Promise<T> {
  for (let attempt = 0; attempt < 120; attempt++) {
    const res = await fetchFresh(url);
    // 202 = the backend is reconciling: keep the last state on screen and
    // show the slim progress bar instead of silently blocking the click.
    if (res.status === 202) {
      ui.reconciling = true;
      await new Promise((r) => setTimeout(r, 500));
      continue;
    }
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    ui.reconciling = false;
    return res.json() as Promise<T>;
  }
  ui.reconciling = false;
  throw new Error('backend busy');
}

function activeFilters(): FilterRow[] {
  return filterState.filters.filter((f) => f.value.trim() !== '');
}

function filterParams(): Record<string, string> {
  const p: Record<string, string> = {
    kind_filter: filterState.kindFilter,
    logic_mode: filterState.logicMode,
  };
  if (filterState.hideStale) p.hide_stale = '1';
  if (filterState.offlineFilter !== 'all') p.offline_filter = filterState.offlineFilter;
  if (filterState.pinnedOnly) p.pinned_only = '1';
  if (filterState.versionFilter) p.version_filter = filterState.versionFilter;
  if (Object.keys(filterState.specFilters).length > 0) p.spec_filters = JSON.stringify(filterState.specFilters);
  const filters = activeFilters();
  if (filters.length > 0) p.filters = JSON.stringify(filters);
  return p;
}

// ---------------------------------------------------------------------------
// Data loading — classes, entry pages, entry detail
// ---------------------------------------------------------------------------

const PAGE = 50;
// Detailed pages are also capped by param rows: wide classes (100+ rows per
// entry) would otherwise ship and lay out thousands of rows per page. The first
// page only needs to fill the screen; scrolling pulls in the rest.
const PAGE_MAX_ROWS = 1500;
const FIRST_PAGE_MAX_ROWS = 200;

function entriesUrl(classes: string[], offset: number): string {
  const q = new URLSearchParams({
    ...filterParams(),
    classes: classes.join(','),
    offset: String(offset),
    limit: String(PAGE),
    row_display: rowDisplay(),
    max_rows: String(offset === 0 ? FIRST_PAGE_MAX_ROWS : PAGE_MAX_ROWS),
  });
  return `/api/class-entries?${q.toString()}`;
}

/** One attempt, no 202 retry: a background prefetch must never hold up a click. */
async function getOnce<T>(url: string): Promise<T> {
  const res = await fetchFresh(url);
  if (res.status !== 200) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

/**
 * Shares in-flight and finished requests by key. A click reuses a pending
 * prefetch, and falls back to a retrying fetch if that prefetch fails.
 */
function shared<T>(cache: Map<string, Promise<T>>, key: string, url: string, prefetch: boolean): Promise<T> {
  const existing = cache.get(key);
  if (existing) return prefetch ? existing : existing.catch(() => shared(cache, key, url, false));
  const req = prefetch ? getOnce<T>(url) : getRetry<T>(url);
  cache.set(key, req);
  req.catch(() => {
    if (cache.get(key) === req) cache.delete(key);
  });
  return req;
}

function fetchFirstPage(classes: string[], prefetch = false): Promise<EntriesPagePayload> {
  const url = entriesUrl(classes, 0);
  const page = shared(firstPageCache, url, url, prefetch);
  if (firstPageCache.size > FIRST_PAGE_CACHE_SIZE) firstPageCache.delete(firstPageCache.keys().next().value!);
  return page;
}

function fetchDetail(recordId: string, prefetch = false): Promise<DetailPayload> {
  const cached = detailCache.get(recordId);
  if (cached) return Promise.resolve(cached);
  const req = shared(detailInflight, recordId, `/api/entry/${encodeURIComponent(recordId)}`, prefetch);
  req
    .then((d) => {
      detailCache.set(recordId, d);
      detailInflight.delete(recordId);
    })
    .catch(() => {});
  return req;
}

/** Hover prefetch: warm the first page and first entry a class click would load. */
export function prefetchClass(className: string) {
  if (selection.multiClass || !ui.ready || ui.reconciling) return;
  fetchFirstPage([className], true)
    .then((page) => {
      const first = page.table_rows.find((r) => r.row_type === 'header');
      if (first) void fetchDetail(first.record_id, true).catch(() => {});
    })
    .catch(() => {});
}

let classesSeq = 0;

export async function refreshClasses() {
  const seq = ++classesSeq;
  const q = new URLSearchParams(filterParams());
  let data: ClassesPayload;
  try {
    data = await getRetry<ClassesPayload>(`/api/classes?${q.toString()}`);
  } catch (err) {
    console.error('classes refresh failed', err);
    toast('Failed to refresh classes');
    return;
  }
  if (seq !== classesSeq) return;
  classesState.cards = data.class_cards;
  classesState.specOptions = data.spec_options;
  classesState.versionOptions = data.version_options;
  classesState.counts = data.counts;
  classesState.diagnostics = data.diagnostics;
  classesState.catalog = data.catalog;
  // Nothing offline any more (the root came back): the filter has no control left to reset it.
  if (filterState.offlineFilter !== 'all' && !data.diagnostics.offline_entries) {
    filterState.offlineFilter = 'all';
    void loadEntries(0, true);
  }
  if (filterState.versionFilter && !data.version_options.some((o) => o.version_id === filterState.versionFilter)) {
    filterState.versionFilter = null;
  }
}

let entriesSeq = 0;

async function loadEntries(offset: number, replace: boolean) {
  if (tableState.selectedClasses.length === 0 && !filterState.pinnedOnly) {
    ++entriesSeq;
    tableState.rows = [];
    tableState.total = 0;
    tableState.loadedCount = 0;
    tableState.fullyLoaded = false;
    tableState.loading = false;
    return;
  }
  const seq = ++entriesSeq;
  tableState.loading = true;
  try {
    const classes = tableState.selectedClasses;
    let data: EntriesPagePayload;
    try {
      data = await (offset === 0 ? fetchFirstPage(classes) : getRetry<EntriesPagePayload>(entriesUrl(classes, offset)));
    } catch (err) {
      console.error('entries page failed', err);
      toast('Failed to load entries');
      return;
    }
    if (seq !== entriesSeq) return;
    const headerCount = data.table_rows.filter((r) => r.row_type === 'header').length;
    tableState.total = data.total;
    tableState.loadedCount = offset + headerCount;
    tableState.fullyLoaded = tableState.loadedCount >= data.total;
    tableState.rows = replace ? data.table_rows : [...tableState.rows, ...data.table_rows];
  } finally {
    if (seq === entriesSeq) tableState.loading = false;
  }
}

let detailSeq = 0;

async function loadDetail(recordId: string) {
  detailState.failed = false;
  const cached = detailCache.get(recordId);
  if (cached) {
    ++detailSeq;
    detailState.loading = false;
    detailState.current = cached;
    return;
  }
  const seq = ++detailSeq;
  detailState.loading = true;
  try {
    const data = await fetchDetail(recordId);
    if (seq === detailSeq && tableState.selectedEntry === recordId) detailState.current = data;
  } catch (err) {
    console.error('entry detail failed', err);
    if (seq === detailSeq) detailState.failed = true;
  } finally {
    if (seq === detailSeq) detailState.loading = false;
  }
}

/** Focus an entry in the table and load its detail; null clears the focus. */
export async function selectEntry(recordId: string | null) {
  if (!recordId) {
    ++detailSeq;
    tableState.selectedEntry = null;
    detailState.current = null;
    detailState.loading = false;
    pushHistory();
    return;
  }
  tableState.selectedEntry = recordId; // optimistic focus highlight
  pushHistory();
  await loadDetail(recordId);
}

/**
 * Jump to an entry that may belong to another class (linked entries, co-outputs,
 * siblings): the owning class joins (multi-select) or replaces the selection.
 */
export async function openEntry(recordId: string, className?: string | null) {
  if (!className || tableState.selectedClasses.includes(className)) {
    await selectEntry(recordId);
    return;
  }
  const card = classesState.cards.find((c) => c.class_name === className);
  if (card && filterState.kindFilter !== 'all' && card.object_type.toLowerCase() !== filterState.kindFilter) {
    filterState.kindFilter = 'all';
    void refreshClasses();
  }
  const classes = selection.multiClass ? [...tableState.selectedClasses, className] : [className];
  await selectClasses(classes, { autoOpen: false, focus: recordId });
}

let selectClassesSeq = 0;

export async function selectClasses(classes: string[], opts: { autoOpen?: boolean; focus?: string | null } = {}) {
  const seq = ++selectClassesSeq;
  tableState.selectedClasses = classes;
  tableState.rows = [];
  tableState.total = 0;
  tableState.loadedCount = 0;
  tableState.fullyLoaded = false;
  tableState.selectedEntry = opts.focus ?? null;
  detailState.current = null;
  ++detailSeq;
  pushHistory();
  const detail = opts.focus ? loadDetail(opts.focus) : null;
  await loadEntries(0, true);
  await detail;
  // Clicking a class auto-opens its first entry.
  if (!opts.focus && opts.autoOpen !== false && classes.length > 0 && seq === selectClassesSeq) {
    const first = tableState.rows.find((r) => r.row_type === 'header');
    if (first) await selectEntry(first.record_id);
  }
}

/** Class-list click: single-select toggle, or add/remove with Multi-select or ⌘/Ctrl. */
export async function toggleClass(className: string, additive = false) {
  const current = tableState.selectedClasses;
  if (selection.multiClass || additive) {
    await selectClasses(
      current.includes(className) ? current.filter((c) => c !== className) : [...current, className],
    );
  } else {
    await selectClasses(current.length === 1 && current[0] === className ? [] : [className]);
  }
}

/** Navigate to a class from a link (dependency lists, JSON explorer): resets a conflicting kind tab. */
export async function navigateToClass(className: string) {
  const card = classesState.cards.find((c) => c.class_name === className);
  if (card && filterState.kindFilter !== 'all' && card.object_type.toLowerCase() !== filterState.kindFilter) {
    filterState.kindFilter = 'all';
    void refreshClasses();
  }
  setView('entries');
  await selectClasses(selection.multiClass ? [...new Set([...tableState.selectedClasses, className])] : [className]);
}

export async function loadMoreEntries() {
  if (tableState.loading || tableState.fullyLoaded || tableState.selectedClasses.length === 0) return;
  await loadEntries(tableState.loadedCount, false);
}

export async function showAllEntries() {
  while (!tableState.fullyLoaded) {
    const before = tableState.loadedCount;
    await loadEntries(tableState.loadedCount, false);
    if (tableState.loadedCount === before) break;
  }
}

// ---------------------------------------------------------------------------
// Filter setters: refresh class counts, reset entry pagination
// ---------------------------------------------------------------------------

async function onFilterChange() {
  await Promise.all([refreshClasses(), loadEntries(0, true)]);
}

export async function setKindFilter(kind: KindFilter) {
  filterState.kindFilter = kind;
  await onFilterChange();
}

export async function setEntriesMode(mode: EntriesMode) {
  if (mode === layout.entriesMode) return;
  layout.entriesMode = mode;
  await loadEntries(0, true);
}

export async function setParamDisplay(mode: ParamDisplay) {
  filterState.paramDisplay = mode;
  await loadEntries(0, true);
}

export async function setLogicMode(mode: LogicMode) {
  filterState.logicMode = mode;
  await onFilterChange();
}

let filterTimer: ReturnType<typeof setTimeout> | null = null;

/** Filter rows (blank rows are kept for editing but never sent). Typing is debounced. */
export function setFilters(filters: FilterRow[], opts: { debounce?: boolean } = {}) {
  const before = JSON.stringify(activeFilters());
  filterState.filters = filters;
  if (JSON.stringify(activeFilters()) === before) return;
  if (filterTimer) clearTimeout(filterTimer);
  if (opts.debounce) {
    filterTimer = setTimeout(() => void onFilterChange(), 200);
  } else {
    void onFilterChange();
  }
}

export async function toggleSpecFilter(dimension: string, value: string) {
  const current = filterState.specFilters[dimension] ?? [];
  const next = current.includes(value) ? current.filter((v) => v !== value) : [...current, value];
  const nextFilters = { ...filterState.specFilters, [dimension]: next };
  if (next.length === 0) delete nextFilters[dimension];
  filterState.specFilters = nextFilters;
  await onFilterChange();
}

export async function setVersionFilter(versionId: string | null) {
  filterState.versionFilter = versionId;
  await onFilterChange();
}

export async function setOfflineFilter(filter: OfflineFilter) {
  filterState.offlineFilter = filter;
  await onFilterChange();
}

export async function toggleHideStale() {
  filterState.hideStale = !filterState.hideStale;
  store('hide_stale', String(filterState.hideStale));
  await onFilterChange();
}

export function hasActiveFilters(): boolean {
  return (
    tableState.selectedClasses.length > 0 ||
    Object.values(filterState.specFilters).some((v) => v.length > 0) ||
    !!filterState.versionFilter ||
    activeFilters().length > 0
  );
}

/** Clear all: classes, spec pills, snapshot and text filters (kind tab is navigation, not a filter). */
export async function clearAllFilters() {
  filterState.filters = [];
  filterState.specFilters = {};
  filterState.versionFilter = null;
  tableState.selectedClasses = [];
  tableState.selectedEntry = null;
  detailState.current = null;
  ++detailSeq;
  pushHistory();
  await onFilterChange();
}

export async function setMultiClass(on: boolean) {
  selection.multiClass = on;
  // Collapsing to single-select keeps only the last selected class.
  if (!on && tableState.selectedClasses.length > 1) {
    await selectClasses([tableState.selectedClasses[tableState.selectedClasses.length - 1]], { autoOpen: false });
  }
}

export function toggleSelectMode() {
  selection.selectMode = !selection.selectMode;
}

/** Optimistically drop an entry (deleted on disk) before the reload confirms it. */
export function forgetEntry(recordId: string) {
  const before = tableState.rows.length;
  tableState.rows = tableState.rows.filter((r) => r.record_id !== recordId);
  if (tableState.rows.length !== before) {
    tableState.total = Math.max(0, tableState.total - 1);
    tableState.loadedCount = Math.max(0, tableState.loadedCount - 1);
  }
  selection.selectedEntries = selection.selectedEntries.filter((id) => id !== recordId);
  detailCache.delete(recordId);
  firstPageCache.clear();
}

export function toggleSelectedEntry(recordId: string) {
  selection.selectedEntries = selection.selectedEntries.includes(recordId)
    ? selection.selectedEntries.filter((id) => id !== recordId)
    : [...selection.selectedEntries, recordId];
}

// ---------------------------------------------------------------------------
// Selection history (⌘[ back / ⌘] forward) and arrow-key entry navigation
// ---------------------------------------------------------------------------

interface Snapshot {
  selectedClasses: string[];
  selectedEntry: string | null;
}

const history: Snapshot[] = [];
let historyIndex = -1;
let restoring = false;

function pushHistory() {
  if (restoring) return;
  const snap: Snapshot = {
    selectedClasses: [...tableState.selectedClasses],
    selectedEntry: tableState.selectedEntry,
  };
  const current = history[historyIndex];
  if (
    current &&
    current.selectedClasses.join(',') === snap.selectedClasses.join(',') &&
    current.selectedEntry === snap.selectedEntry
  ) {
    return;
  }
  history.splice(historyIndex + 1);
  history.push(snap);
  if (history.length > 100) history.shift();
  historyIndex = history.length - 1;
}

async function restore(snap: Snapshot) {
  restoring = true;
  try {
    setView('entries');
    if (snap.selectedClasses.join(',') !== tableState.selectedClasses.join(',')) {
      await selectClasses(snap.selectedClasses, { autoOpen: false, focus: snap.selectedEntry });
    } else {
      await selectEntry(snap.selectedEntry);
    }
  } finally {
    restoring = false;
  }
}

export async function navigateBack() {
  if (historyIndex <= 0) return;
  historyIndex -= 1;
  await restore(history[historyIndex]);
}

export async function navigateForward() {
  if (historyIndex >= history.length - 1) return;
  historyIndex += 1;
  await restore(history[historyIndex]);
}

export async function selectAdjacentEntry(delta: 1 | -1) {
  const ids = tableState.rows.filter((r) => r.row_type === 'header').map((r) => r.record_id);
  if (ids.length === 0) return;
  const cur = ids.indexOf(tableState.selectedEntry ?? '');
  const nextIndex = cur === -1 ? (delta === 1 ? 0 : ids.length - 1) : Math.min(Math.max(cur + delta, 0), ids.length - 1);
  // Keep paging in when the arrow walk reaches the end of the loaded pages.
  if (nextIndex === ids.length - 1 && !tableState.fullyLoaded) void loadMoreEntries();
  await selectEntry(ids[nextIndex]);
}

// ---------------------------------------------------------------------------
// Rebuild / status polling
// ---------------------------------------------------------------------------

export async function startReload() {
  try {
    await api.rebuild();
  } catch (err) {
    toast(`Reload failed: ${err}`);
    return;
  }
  ui.loading = true;
  ui.ready = false;
  pollStatus();
}

/** The backend already started a reload (entry delete, clean): poll until the new state is in. */
export function followServerReload() {
  ui.loading = true;
  ui.ready = false;
  pollStatus();
}

let statusTimer: ReturnType<typeof setTimeout> | null = null;

async function onReady() {
  const firstLoad = !ui.ready && classesState.cards.length === 0;
  ui.loading = false;
  ui.ready = true;
  ui.overlay = false;
  ui.bootstrap = [];
  clearCaches();
  void loadPins();
  await refreshClasses();
  if (tableState.selectedClasses.length > 0) {
    const known = new Set(classesState.cards.map((c) => c.class_name));
    tableState.selectedClasses = tableState.selectedClasses.filter((c) => known.has(c));
    await loadEntries(0, true);
  }
  const rid = tableState.selectedEntry;
  if (rid && !firstLoad) {
    if (tableState.rows.some((r) => r.record_id === rid)) await loadDetail(rid);
    else await selectEntry(null);
  }
}

function applyStatus(status: StatusPayload) {
  ui.loadError = status.load_error;
  ui.hasLiveClasses = status.has_live_classes;
  ui.mode = status.mode;
  ui.codeChangedSince = status.code_changed_since;
  ui.nextImportAt = status.next_import_at;
}

export function pollStatus() {
  if (statusTimer) clearTimeout(statusTimer);
  const check = async () => {
    statusTimer = null;
    try {
      const status: StatusPayload = await api.status();
      ui.fast = status.fast;
      if (!ui.statusKnown && !status.fast && !status.ready) ui.overlay = true;
      ui.statusKnown = true;
      applyStatus(status);
      if (status.ready) {
        await onReady();
        return;
      }
    } catch {
      /* backend briefly unreachable during dev reloads */
    }
    statusTimer = setTimeout(check, 300);
  };
  void check();
}

export async function init() {
  applyTheme();
  pollStatus();
  pollIdleVersion();
  // Bootstrap rows (latest entry per class, ~2 MB) only bridge a still-building state.
  try {
    if ((await api.status()).ready) return;
    const rows = await api.bootstrap();
    if (!ui.ready) ui.bootstrap = rows;
  } catch {
    /* the status poll keeps retrying */
  }
}

// ---------------------------------------------------------------------------
// Idle version poll — the backend swaps in a new state offscreen (periodic
// reconcile); this quietly refreshes the visible data when it does.
// ---------------------------------------------------------------------------

let seenVersion: number | null = null;
let idleTimer: ReturnType<typeof setTimeout> | null = null;
const IDLE_POLL_MS = 5000;

function pollIdleVersion() {
  const check = async () => {
    idleTimer = null;
    try {
      const status: StatusPayload = await api.status();
      const changed = seenVersion !== null && status.version !== seenVersion;
      seenVersion = status.version;
      applyStatus(status);
      // Only refresh visible data once the initial state is fully built; the
      // loading poll handles transitions into ready.
      if (changed && status.ready && ui.ready) {
        await onReady();
      }
    } catch {
      /* backend briefly unreachable */
    }
    idleTimer = setTimeout(check, IDLE_POLL_MS);
  };
  void check();
}
