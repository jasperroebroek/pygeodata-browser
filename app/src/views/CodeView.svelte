<script lang="ts">
  import { app, selectClasses } from '../lib/stores.svelte';
  import {
    codeApi,
    isLoading,
    type CodeClassState,
    type CodeVersion,
    type DiffPayload,
    type SnapshotPayload,
    type VersionChange,
    type VersionDiffPayload,
  } from '../lib/apiCode';
  import DiffTable from '../components/code/DiffTable.svelte';
  import SnapshotTable from '../components/code/SnapshotTable.svelte';
  import ChangeSummary from '../components/code/ChangeSummary.svelte';

  type BrowseMode = 'version' | 'class';
  type CodeKind = 'all' | 'data' | 'table' | 'figure' | 'trackedobject';

  interface DiffOption {
    label: string;
    hash_old: string;
    hash_new: string;
  }

  let versions = $state<CodeVersion[]>([]);
  let hasLiveClasses = $state(false);
  let hasLiveStale = $state(false);
  let liveChanges = $state<VersionChange[] | null>(null);
  let versionsLoading = $state(true);

  let allClasses = $state<CodeClassState[]>([]);
  let versionClasses = $state<CodeClassState[]>([]);
  let selectedVersion = $state<string | null>(null); // version_id or 'live'
  let selectedClass = $state<string | null>(null);

  let browseMode = $state<BrowseMode>(
    localStorage.getItem('code_browse_mode') === 'class' ? 'class' : 'version',
  );
  let kindFilter = $state<CodeKind>('all');
  let classFilter = $state('');
  let allClassFilter = $state('');
  let hideEmpty = $state(localStorage.getItem('hide_empty_versions') === 'true');

  let diffViewMode = $state<'inline' | 'split'>(
    localStorage.getItem('diff_view_mode') === 'split' ? 'split' : 'inline',
  );
  let diffExpand = $state<'hunks' | 'full'>(
    localStorage.getItem('diff_expand') === 'full' ? 'full' : 'hunks',
  );

  // Source pane: 'none' | 'class' (snapshot/class-diff) | 'summary' (version diff)
  let sourceMode = $state<'none' | 'class' | 'summary'>('none');
  let snapshot = $state<SnapshotPayload | null>(null);
  let snapshotError = $state(false);
  let classDiff = $state<DiffPayload | null>(null);
  let diffOptions = $state<DiffOption[]>([]);
  let diffOptionIdx = $state(0);
  let summary = $state<VersionDiffPayload | null>(null);
  let summaryTarget = $state<string>('live');
  let summaryBase = $state<string>('none');
  let summaryError = $state<string | null>(null);
  let summaryLoading = $state(false);
  let summaryDiffs = $state<Record<string, DiffPayload | null>>({});

  let note = $state('');
  let noteTimer: ReturnType<typeof setTimeout> | undefined;
  let selectSeq = 0;
  let loadSeq = 0;

  const kinds: { key: CodeKind; label: string }[] = [
    { key: 'all', label: 'All' },
    { key: 'data', label: 'Data' },
    { key: 'table', label: 'Table' },
    { key: 'figure', label: 'Figure' },
    { key: 'trackedobject', label: 'Object' },
  ];

  function flashNote(message: string) {
    note = message;
    if (noteTimer) clearTimeout(noteTimer);
    noteTimer = setTimeout(() => (note = ''), 2600);
  }

  function clearClassDiff() {
    classDiff = null;
  }

  function byKind(list: CodeClassState[]): CodeClassState[] {
    if (kindFilter === 'all') return list;
    return list.filter((c) => (c.object_type ?? '').toLowerCase() === kindFilter);
  }

  function byFilter(list: CodeClassState[], filter: string): CodeClassState[] {
    const f = filter.toLowerCase();
    return f ? list.filter((c) => c.class_name.toLowerCase().includes(f)) : list;
  }

  // ---------------------------------------------------------------------------
  // Loading
  // ---------------------------------------------------------------------------

  async function load() {
    const mySeq = ++loadSeq;
    try {
      const resp = await codeApi.versions();
      if (isLoading(resp)) {
        setTimeout(() => void load(), 600);
        return;
      }
      if (mySeq !== loadSeq) return;
      versions = resp.versions;
      hasLiveClasses = resp.has_live_classes;
      hasLiveStale = false;
      if (hasLiveClasses && versions.length) {
        try {
          const liveCheck = await codeApi.versionDiff({
            base_version_id: versions[0].version_id,
            target_version_id: 'live',
          });
          if (mySeq === loadSeq) {
            hasLiveStale = !!liveCheck.has_live_stale;
            liveChanges = liveCheck.changes ?? [];
          }
        } catch {
          /* leave stale flag off */
        }
      }
      if (mySeq !== loadSeq) return;
      versionsLoading = false;
      if (browseMode === 'class') await ensureAllClasses();
    } catch {
      versionsLoading = false;
      flashNote('Could not load code versions');
    }
  }

  async function ensureAllClasses(): Promise<CodeClassState[]> {
    if (!allClasses.length && versions.length) {
      allClasses = await codeApi.versionClasses(versions[0].version_id);
    }
    return allClasses;
  }

  // ---------------------------------------------------------------------------
  // Version selection
  // ---------------------------------------------------------------------------

  async function selectVersion(versionId: string) {
    const mySeq = ++selectSeq;
    selectedVersion = versionId;
    selectedClass = null;
    summary = null;
    summaryError = null;
    clearClassDiff();
    snapshot = null;
    const meta = versions.find((v) => v.version_id === versionId);
    try {
      const classes = await codeApi.versionClasses(versionId);
      if (mySeq !== selectSeq) return;
      versionClasses = classes;
    } catch {
      flashNote('Could not load version');
      return;
    }
    const changed = meta?.changed_class_names ?? [];
    if (changed.length) {
      // Versions with changed classes show a diff overview instead of auto-selecting a class.
      await showVersionDiff(versionId, null);
      return;
    }
    if (versionClasses.length) await selectClass(versionClasses[0]);
  }

  async function selectLiveVersion() {
    selectedVersion = 'live';
    selectedClass = null;
    summary = null;
    summaryError = null;
    clearClassDiff();
    snapshot = null;
    if (versions.length) {
      try {
        versionClasses = await ensureAllClasses();
      } catch {
        flashNote('Could not load classes');
      }
    }
    await showVersionDiff('live', versions[0]?.version_id ?? null);
  }

  // ---------------------------------------------------------------------------
  // Version diff (source pane summary)
  // ---------------------------------------------------------------------------

  async function showVersionDiff(target: string, base: string | null) {
    const mySeq = ++selectSeq;
    const targetId = target ?? (hasLiveClasses ? 'live' : (versions[0]?.version_id ?? 'live'));
    const targetIdx = targetId === 'live' ? -1 : versions.findIndex((v) => v.version_id === targetId);
    const defaultBase =
      targetId === 'live'
        ? (versions[0]?.version_id ?? 'none') // Live → compare with newest registered
        : (versions[targetIdx + 1]?.version_id ?? 'none'); // vN → compare with predecessor (or empty)
    const baseId = base ?? defaultBase;
    selectedClass = null;
    clearClassDiff();
    snapshot = null;
    diffOptions = [];
    summary = null;
    summaryError = null;
    summaryDiffs = {};
    summaryLoading = true;
    sourceMode = 'summary';
    try {
      const result = await codeApi.versionDiff({ base_version_id: baseId, target_version_id: targetId });
      if (mySeq !== selectSeq) return;
      summaryLoading = false;
      if (result.error) {
        summaryError = result.message ?? result.error;
        return;
      }
      summary = result;
      summaryTarget = targetId;
      summaryBase = result.base_version_id ?? baseId;
      hasLiveStale = !!result.has_live_stale;
    } catch {
      if (mySeq !== selectSeq) return;
      summaryLoading = false;
      summaryError = 'Could not load diff.';
    }
  }

  function handleSummaryDiff(cls: string, diff: DiffPayload | null) {
    summaryDiffs[cls] = diff;
  }

  // ---------------------------------------------------------------------------
  // Class selection (source snapshot)
  // ---------------------------------------------------------------------------

  async function selectClass(entry: CodeClassState) {
    const mySeq = ++selectSeq;
    selectedClass = entry.class_name;
    summary = null;
    summaryError = null;
    summaryLoading = false;
    snapshot = null;
    snapshotError = false;
    diffOptions = [];
    diffOptionIdx = 0;
    clearClassDiff();
    sourceMode = 'class';
    const [snap, opts] = await Promise.all([
      codeApi.snapshot(entry.source_hash).catch(() => null),
      buildDiffOptions(entry),
    ]);
    if (mySeq !== selectSeq) return;
    diffOptions = opts;
    if (snap) snapshot = snap;
    else snapshotError = true;
  }

  async function buildDiffOptions(entry: CodeClassState): Promise<DiffOption[]> {
    const opts: DiffOption[] = [];
    const effectiveIdx =
      selectedVersion === 'live' ? 0 : versions.findIndex((v) => v.version_id === selectedVersion);
    const prevVersion = effectiveIdx >= 0 ? (versions[effectiveIdx + 1] ?? null) : null;
    const isViewingCurrent =
      selectedVersion === 'live' || (versions.length > 0 && selectedVersion === versions[0].version_id);

    if (prevVersion) {
      try {
        const classes = await codeApi.versionClasses(prevVersion.version_id);
        const match = classes.find((c) => c.class_name === entry.class_name);
        if (match && match.source_hash !== entry.source_hash) {
          opts.push({
            label: prevVersion.label,
            hash_old: match.source_hash,
            hash_new: entry.source_hash,
          });
        }
      } catch {
        /* skip option */
      }
    }

    if (!isViewingCurrent && versions.length) {
      try {
        const current = (await ensureAllClasses()).find((c) => c.class_name === entry.class_name);
        if (current && current.source_hash !== entry.source_hash) {
          opts.push({
            label: hasLiveClasses ? 'Live' : versions[0].label,
            hash_old: entry.source_hash,
            hash_new: current.source_hash,
          });
        }
      } catch {
        /* skip option */
      }
    }

    // Viewing the newest version: offer a Live compare for classes whose
    // in-memory source diverged from the newest registered version.
    if (isViewingCurrent && hasLiveClasses && liveChanges) {
      const ch = liveChanges.find(
        (c) => c.class_name === entry.class_name && c.status === 'changed' && c.hash_new,
      );
      if (ch && ch.hash_new !== entry.source_hash) {
        opts.push({
          label: 'Live',
          hash_old: entry.source_hash,
          hash_new: ch.hash_new as string,
        });
      }
    }

    return opts;
  }

  function onClassClick(entry: CodeClassState) {
    if (entry.class_name === selectedClass) {
      // Deselect — return to the version change summary if this version has changed classes.
      const meta = versions.find((v) => v.version_id === selectedVersion);
      if (meta?.changed_class_names?.length) void showVersionDiff(selectedVersion ?? '', null);
      return;
    }
    void selectClass(entry);
  }

  function onSourceLink(cls: string) {
    const match = versionClasses.find((c) => c.class_name === cls);
    if (match) void selectClass(match);
  }

  // ---------------------------------------------------------------------------
  // Class diff mode (per-class compare)
  // ---------------------------------------------------------------------------

  async function enterDiffMode() {
    if (!diffOptions.length) {
      flashNote('No previous version to diff against');
      return;
    }
    diffOptionIdx = 0;
    await loadClassDiff(diffOptions[0]);
  }

  async function loadClassDiff(opt: DiffOption) {
    const mySeq = ++selectSeq;
    try {
      const data = await codeApi.diff(opt.hash_old, opt.hash_new, true);
      if (mySeq !== selectSeq) return;
      classDiff = data;
    } catch {
      flashNote('Diff unavailable');
    }
  }

  function exitDiffMode() {
    clearClassDiff();
  }

  function onDiffOptionChange(event: Event) {
    const idx = Number((event.currentTarget as HTMLSelectElement).value);
    diffOptionIdx = idx;
    void loadClassDiff(diffOptions[idx]);
  }

  function onSummaryBaseChange(event: Event) {
    void showVersionDiff(summaryTarget, (event.currentTarget as HTMLSelectElement).value);
  }

  function setDiffViewMode(mode: 'inline' | 'split') {
    diffViewMode = mode;
    localStorage.setItem('diff_view_mode', mode);
  }

  function setDiffExpand(mode: 'hunks' | 'full') {
    diffExpand = mode;
    localStorage.setItem('diff_expand', mode);
  }

  // ---------------------------------------------------------------------------
  // Class-first browse mode
  // ---------------------------------------------------------------------------

  async function selectClassFirst(entry: CodeClassState) {
    selectedClass = entry.class_name;
    const relevant = versions.filter((v) => (v.class_names ?? []).includes(entry.class_name));
    if (relevant.length) {
      const newest = relevant[0];
      selectedVersion = newest.version_id;
      try {
        const classes = await codeApi.versionClasses(newest.version_id);
        versionClasses = classes;
        const match = classes.find((c) => c.class_name === entry.class_name);
        if (match) {
          await selectClass(match);
          return;
        }
      } catch {
        flashNote('Could not load version');
      }
    }
    await selectClass(entry);
  }

  async function selectVersionForClass(versionId: string, className: string) {
    selectedVersion = versionId;
    try {
      const classes = await codeApi.versionClasses(versionId);
      versionClasses = classes;
      const match = classes.find((c) => c.class_name === className);
      if (match) await selectClass(match);
    } catch {
      flashNote('Could not load version');
    }
  }

  async function applyBrowseMode(mode: BrowseMode) {
    browseMode = mode;
    localStorage.setItem('code_browse_mode', mode);
    if (mode === 'version') {
      const target = selectedVersion ?? versions[0]?.version_id ?? null;
      if (target === 'live') await selectLiveVersion();
      else if (target) await selectVersion(target);
    } else {
      try {
        await ensureAllClasses();
      } catch {
        flashNote('Could not load classes');
      }
      if (selectedClass) return;
      if (allClasses.length) await selectClassFirst(allClasses[0]);
    }
  }

  // ---------------------------------------------------------------------------
  // Find in entries
  // ---------------------------------------------------------------------------

  async function findInEntries() {
    if (!selectedClass) return;
    app.view = 'entries';
    await selectClasses([selectedClass]);
  }

  function setHideEmpty(hide: boolean) {
    hideEmpty = hide;
    localStorage.setItem('hide_empty_versions', hide ? 'true' : 'false');
  }

  // ---------------------------------------------------------------------------
  // Derived view state
  // ---------------------------------------------------------------------------

  const visibleVersions = $derived(hideEmpty ? versions.filter((v) => v.has_entries) : versions);

  const visibleVersionClasses = $derived(
    byFilter(byKind(versionClasses), classFilter),
  );
  const visibleAllClasses = $derived(byFilter(byKind(allClasses), allClassFilter));

  const versionsForClass = $derived(
    selectedClass ? versions.filter((v) => (v.class_names ?? []).includes(selectedClass as string)) : [],
  );

  const summaryChanges = $derived(summary?.changes ?? []);

  const inSummary = $derived(sourceMode === 'summary');
  const inClassDiff = $derived(classDiff !== null);

  const showDiffBar = $derived((sourceMode === 'class' && diffOptions.length > 0) || inSummary);
  const modeSegEnabled = $derived(inClassDiff || inSummary);
  const anySummaryFull = $derived(
    Object.values(summaryDiffs).some((d) => d !== null && d !== undefined && !!d.full_old),
  );
  const expandSegEnabled = $derived(inClassDiff ? !!classDiff?.full_old : inSummary && anySummaryFull);

  const title = $derived.by(() => {
    if (sourceMode === 'class') return selectedClass ?? '';
    if (inSummary) {
      return summaryTarget === 'live'
        ? 'Live'
        : (versions.find((v) => v.version_id === summaryTarget)?.label ?? '');
    }
    return '';
  });

  const baseOptions = $derived([
    ...(hasLiveClasses ? [{ value: 'live', label: 'Live' }] : []),
    ...versions.map((v) => ({ value: v.version_id, label: v.label })),
    { value: 'none', label: '(empty)' },
  ]);

  $effect(() => {
    void load();
  });
</script>

<section class="code">
  <div class="toolbar">
    <div class="seg">
      <button class:active={browseMode === 'version'} onclick={() => applyBrowseMode('version')}
        >By version</button
      >
      <button class:active={browseMode === 'class'} onclick={() => applyBrowseMode('class')}
        >By class</button
      >
    </div>
    <div class="seg">
      {#each kinds as k}
        <button class:active={kindFilter === k.key} onclick={() => (kindFilter = k.key)}>{k.label}</button>
      {/each}
    </div>
    <div class="spacer"></div>
    {#if browseMode === 'version'}
      <button class="toggle" class:active={hideEmpty} onclick={() => setHideEmpty(!hideEmpty)}
        >Hide empty</button
      >
    {/if}
  </div>

  <div class="panes">
    <!-- Left pane: versions (version mode) or all classes (class mode) -->
    <aside class="pane">
      {#if browseMode === 'class'}
        <div class="filter">
          <input type="search" placeholder="Filter classes…" bind:value={allClassFilter} />
        </div>
      {/if}
      <div class="list">
        {#if versionsLoading}
          <div class="empty">loading…</div>
        {:else if browseMode === 'version'}
          {#if hasLiveClasses}
            <button
              class="item"
              class:active={selectedVersion === 'live'}
              onclick={() => void selectLiveVersion()}
            >
              Live
              {#if hasLiveStale}<span class="stale" title="In-memory code differs from disk"></span>{/if}
            </button>
          {/if}
          {#if visibleVersions.length === 0}
            {#if hideEmpty && versions.length}
              <div class="empty">
                All versions are empty. <button class="link" onclick={() => setHideEmpty(false)}
                  >Show all</button
                >
              </div>
            {:else}
              <div class="empty">No code snapshots found.</div>
            {/if}
          {/if}
          {#each visibleVersions as v (v.version_id)}
            <button
              class="item"
              class:active={v.version_id === selectedVersion}
              onclick={() => void selectVersion(v.version_id)}
            >
              {v.label}
            </button>
          {/each}
        {:else}
          {#if visibleAllClasses.length === 0}
            <div class="empty">No classes.</div>
          {/if}
          {#each visibleAllClasses as c (c.class_name)}
            <button
              class="item class-item"
              class:active={c.class_name === selectedClass}
              onclick={() => void selectClassFirst(c)}
            >
              <span class="name"
                >{c.class_name}{#if c.is_stale}<span
                    class="stale"
                    title="Source changed since this version"
                  ></span
                >{/if}</span
              >
              <span class="type kind-{(c.object_type ?? '').toLowerCase()}">{c.object_type}</span>
            </button>
          {/each}
        {/if}
      </div>
    </aside>

    <!-- Middle pane: classes of the version (version mode) or versions of the class (class mode) -->
    <aside class="pane">
      {#if browseMode === 'version'}
        <div class="filter">
          <input type="search" placeholder="Filter…" bind:value={classFilter} />
        </div>
      {/if}
      <div class="list">
        {#if browseMode === 'version'}
          {#if visibleVersionClasses.length === 0}
            <div class="empty">No classes.</div>
          {/if}
          {#each visibleVersionClasses as c (c.class_name)}
            <button
              class="item class-item"
              class:active={c.class_name === selectedClass}
              onclick={() => onClassClick(c)}
            >
              <span class="name"
                >{c.class_name}{#if c.is_stale}<span
                    class="stale"
                    title="Source changed since this version"
                  ></span
                >{/if}</span
              >
              <span class="type kind-{(c.object_type ?? '').toLowerCase()}">{c.object_type}</span>
            </button>
          {/each}
        {:else}
          {#if !selectedClass}
            <div class="empty">Select a class.</div>
          {:else if versionsForClass.length === 0}
            <div class="empty">No snapshots for this class.</div>
          {/if}
          {#each versionsForClass as v (v.version_id)}
            <button
              class="item"
              class:active={v.version_id === selectedVersion}
              onclick={() => void selectVersionForClass(v.version_id, selectedClass as string)}
            >
              {v.label}
            </button>
          {/each}
        {/if}
      </div>
    </aside>

    <!-- Source pane -->
    <div class="pane source">
      <div class="src-head">
        <span class="src-title mono">{title}</span>
        <div class="spacer"></div>
        {#if sourceMode === 'class' && selectedClass}
          <button class="find" onclick={() => void findInEntries()}>Find entries</button>
        {/if}
      </div>

      {#if showDiffBar}
        <div class="diff-bar">
          {#if inSummary}
            <label class="compare">
              Compare with
              <select value={summaryBase} onchange={onSummaryBaseChange}>
                {#each baseOptions as o (o.value)}
                  <option value={o.value}>{o.label}</option>
                {/each}
              </select>
            </label>
          {:else}
            <label class="compare">
              Compare with
              <select value={String(diffOptionIdx)} onchange={onDiffOptionChange}>
                {#each diffOptions as o, i (i)}
                  <option value={String(i)}>{o.label}</option>
                {/each}
              </select>
            </label>
          {/if}
          <div class="seg" class:hidden={inSummary}>
            <button class:active={!inClassDiff} onclick={() => exitDiffMode()}>Source</button>
            <button class:active={inClassDiff} onclick={() => void enterDiffMode()}>Diff</button>
          </div>
          <div class="seg" class:disabled={!modeSegEnabled}>
            <button disabled={!modeSegEnabled} class:active={diffViewMode === 'inline'} onclick={() => setDiffViewMode('inline')}>Inline</button>
            <button disabled={!modeSegEnabled} class:active={diffViewMode === 'split'} onclick={() => setDiffViewMode('split')}>Side by side</button>
          </div>
          <div class="seg" class:disabled={!expandSegEnabled}>
            <button disabled={!expandSegEnabled} class:active={diffExpand === 'hunks'} onclick={() => setDiffExpand('hunks')}>Hunks</button>
            <button disabled={!expandSegEnabled} class:active={diffExpand === 'full'} onclick={() => setDiffExpand('full')}>Full</button>
          </div>
        </div>
      {/if}

      <div class="src-body">
        {#if note}
          <div class="note">{note}</div>
        {/if}
        {#if sourceMode === 'none'}
          <div class="empty">Select a version or a class.</div>
        {:else if sourceMode === 'summary'}
          {#if summaryLoading}
            <div class="empty">Loading diff…</div>
          {:else if summaryError}
            <div class="empty">{summaryError}</div>
          {:else if summaryChanges.length === 0}
            <div class="empty">No changes between these versions.</div>
          {:else}
            <ChangeSummary
              changes={summaryChanges}
              mode={diffViewMode}
              expand={diffExpand}
              onLink={onSourceLink}
              onDiff={handleSummaryDiff}
            />
          {/if}
        {:else if inClassDiff && classDiff}
          <DiffTable diff={classDiff} mode={diffViewMode} expand={diffExpand} />
        {:else if snapshot}
          <SnapshotTable snapshot={snapshot} onLink={onSourceLink} />
        {:else if snapshotError}
          <div class="empty">Source unavailable</div>
        {/if}
      </div>
    </div>
  </div>
</section>

<style>
  .code {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
    width: 100%;
  }

  .toolbar {
    display: flex;
    align-items: center;
    gap: var(--s-3);
    padding: var(--s-1) var(--s-3);
    border-bottom: 1px solid var(--border);
    background: var(--bg-sidebar);
    flex: none;
  }

  .seg {
    display: flex;
    gap: 2px;
  }

  .seg button {
    padding: 3px 10px;
    border-radius: var(--r-sm);
    color: var(--text-2);
    font-size: var(--fs-sm);
  }

  .seg button:hover:not(:disabled) {
    background: var(--bg-hover);
  }

  .seg button.active {
    background: var(--bg-active);
    color: var(--text);
    font-weight: 500;
  }

  .seg button:disabled {
    color: var(--text-3);
    opacity: 0.55;
    cursor: default;
  }

  .spacer {
    flex: 1;
  }

  .toggle {
    padding: 3px 10px;
    border-radius: var(--r-full);
    font-size: var(--fs-sm);
    color: var(--text-2);
    border: 1px solid var(--border-strong);
  }

  .toggle:hover {
    background: var(--bg-hover);
  }

  .toggle.active {
    background: var(--accent-soft);
    color: var(--accent-text);
    border-color: transparent;
  }

  .panes {
    flex: 1;
    min-height: 0;
    display: grid;
    grid-template-columns: 230px 300px minmax(0, 1fr);
  }

  .pane {
    display: flex;
    flex-direction: column;
    min-height: 0;
    min-width: 0;
    background: var(--bg-sidebar);
  }

  .pane:nth-child(1),
  .pane:nth-child(2) {
    border-right: 1px solid var(--border);
  }

  .filter {
    padding: var(--s-2);
    border-bottom: 1px solid var(--border);
  }

  .filter input {
    width: 100%;
    padding: 5px 8px;
    border: 1px solid var(--border-strong);
    border-radius: var(--r-sm);
    background: var(--bg-elev);
    color: var(--text);
    font: inherit;
    font-size: var(--fs-sm);
  }

  .filter input:focus {
    outline: 1.5px solid var(--accent);
    border-color: transparent;
  }

  .list {
    flex: 1;
    overflow-y: auto;
    padding: var(--s-2);
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .item {
    display: block;
    width: 100%;
    text-align: left;
    padding: 5px 8px;
    border-radius: var(--r-sm);
    font-size: var(--fs-sm);
    color: var(--text-2);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .item:hover {
    background: var(--bg-hover);
    color: var(--text);
  }

  .item.active {
    background: var(--bg-selected);
    border: 1px solid var(--accent-soft);
    color: var(--text);
    font-weight: 500;
  }

  .class-item {
    display: flex;
    align-items: center;
    gap: var(--s-2);
  }

  .class-item .name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .class-item .type {
    font-size: var(--fs-xs);
    flex: none;
  }

  .kind-data {
    color: var(--kind-data);
  }

  .kind-figure {
    color: var(--kind-figure);
  }

  .kind-table {
    color: var(--kind-table);
  }

  .kind-trackedobject {
    color: var(--text-3);
  }

  .stale {
    display: inline-block;
    width: 7px;
    height: 7px;
    border-radius: var(--r-full);
    background: var(--warning);
    margin-left: 6px;
    vertical-align: middle;
    flex: none;
  }

  .empty {
    padding: var(--s-3);
    color: var(--text-3);
    font-size: var(--fs-sm);
    text-align: center;
  }

  .link {
    color: var(--link);
    font-size: var(--fs-sm);
  }

  .link:hover {
    text-decoration: underline;
  }

  /* Source pane */

  .source {
    background: var(--bg-panel);
  }

  .src-head {
    display: flex;
    align-items: center;
    gap: var(--s-2);
    padding: var(--s-1) var(--s-3);
    border-bottom: 1px solid var(--border);
    min-height: 34px;
  }

  .src-title {
    font-size: var(--fs-sm);
    font-weight: 500;
    color: var(--text);
  }

  .find {
    padding: 3px 10px;
    border-radius: var(--r-full);
    font-size: var(--fs-sm);
    color: var(--text-2);
    border: 1px solid var(--border-strong);
  }

  .find:hover {
    background: var(--bg-hover);
    color: var(--text);
  }

  .diff-bar {
    display: flex;
    align-items: center;
    gap: var(--s-3);
    padding: var(--s-1) var(--s-3);
    border-bottom: 1px solid var(--border);
    background: var(--bg-sidebar);
    flex: none;
  }

  .compare {
    display: flex;
    align-items: center;
    gap: var(--s-2);
    font-size: var(--fs-sm);
    color: var(--text-2);
  }

  .compare select {
    padding: 3px 6px;
    border: 1px solid var(--border-strong);
    border-radius: var(--r-sm);
    background: var(--bg-elev);
    color: var(--text);
    font: inherit;
    font-size: var(--fs-sm);
    max-width: 200px;
  }

  .hidden {
    display: none;
  }

  .seg.disabled {
    opacity: 0.5;
  }

  .src-body {
    flex: 1;
    min-height: 0;
    overflow: auto;
  }

  .note {
    position: sticky;
    top: 0;
    z-index: 2;
    background: var(--accent-soft);
    color: var(--accent-text);
    font-size: var(--fs-sm);
    padding: var(--s-1) var(--s-3);
    border-radius: 0 0 var(--r-sm) var(--r-sm);
  }
</style>
