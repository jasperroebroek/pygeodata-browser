import { classesState, detailState, navigateToClass, setView, tableState, ui } from './stores.svelte';
import type { View } from './stores.svelte';

export type BrowseMode = 'version' | 'class';
export type CodeKind = 'all' | 'data' | 'table' | 'figure' | 'trackedobject';

export interface CodeTarget {
  className: string;
  depHash?: string | null;
  sourceHash?: string | null;
}

function stored(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

/** Code-view toolbar state; lives here because the top bar renders the controls. */
export const codeUi = $state({
  browseMode: (stored('code_browse_mode') === 'class' ? 'class' : 'version') as BrowseMode,
  kindFilter: 'all' as CodeKind,
  hideEmpty: stored('hide_empty_versions') === 'true',
});

export function setBrowseMode(mode: BrowseMode) {
  codeUi.browseMode = mode;
  localStorage.setItem('code_browse_mode', mode);
}

export function setHideEmpty(hide: boolean) {
  codeUi.hideEmpty = hide;
  localStorage.setItem('hide_empty_versions', hide ? 'true' : 'false');
}

export const codeNav = $state({
  target: null as CodeTarget | null,
  diffRecordId: null as string | null,
  diffClassName: null as string | null,
  versionId: null as string | null,
  /** Class open in the code view; switching to Entries selects it. */
  currentClass: null as string | null,
});

/**
 * Jump to the code view with a class open. depHash routes to the version the
 * entry was computed at; sourceHash pins an exact snapshot.
 */
export function navigateToCodeClass(className: string, opts: { depHash?: string | null; sourceHash?: string | null } = {}) {
  codeNav.target = { className, ...opts };
  codeNav.diffRecordId = null;
  setView('code');
}

/** Jump to the code view with a version selected (browse by version). */
export function navigateToCodeVersion(versionId: string) {
  setBrowseMode('version');
  codeNav.versionId = versionId;
  codeNav.target = null;
  codeNav.diffRecordId = null;
  setView('code');
}

/** Jump to the code view showing what changed in the code since an entry was computed. */
export function showWhatChanged(recordId: string, className: string | null = null) {
  codeNav.diffRecordId = recordId;
  codeNav.diffClassName = className;
  codeNav.target = null;
  setView('code');
}

/** Tab switches carry the class selection between the Entries and Code views. */
export function switchView(view: View) {
  if (view === ui.view) return;
  const selected = tableState.selectedClasses;
  if (view === 'code' && selected.length === 1) {
    const entry = detailState.current?.selected_entry;
    navigateToCodeClass(selected[0], { depHash: entry?.class_name === selected[0] ? entry.dep_hash : null });
    return;
  }
  const cls = codeNav.currentClass;
  const hasEntries = !!cls && classesState.cards.some((c) => c.class_name === cls && c.total_record_count > 0);
  if (view === 'entries' && ui.view === 'code' && hasEntries && !(selected.length === 1 && selected[0] === cls)) {
    void navigateToClass(cls!);
    return;
  }
  setView(view);
}
