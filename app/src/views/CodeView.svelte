<script lang="ts">
  import { untrack } from 'svelte';
  import { filterState, layout, navigateToClass } from '../lib/stores.svelte';
  import { codeNav, codeUi } from '../lib/nav.svelte';
  import { toast } from '../lib/toast.svelte';
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
  import ReloadBar from '../components/ReloadBar.svelte';
  import Resizer from '../components/Resizer.svelte';
  import TypeBadge from '../components/TypeBadge.svelte';
  import DiffTable from '../components/code/DiffTable.svelte';
  import SnapshotTable from '../components/code/SnapshotTable.svelte';
  import ChangeSummary from '../components/code/ChangeSummary.svelte';

  interface DiffOption {
    label: string;
    hash_old: string;
    hash_new: string;
  }

  // Module-level cache: the code view remounts on every tab switch.
  let versions = $state<CodeVersion[]>([]);
  let hasLiveClasses = $state(false);
  let hasLiveStale = $state(false);
  let liveChanges = $state<VersionChange[] | null>(null);
  let versionsLoading = $state(true);

  let allClasses = $state<CodeClassState[]>([]);
  let versionClasses = $state<CodeClassState[]>([]);
  let selectedVersion = $state<string | null>(null); // version_id or 'live'
  let selectedClass = $state<string | null>(null);

  $effect(() => {
    codeNav.currentClass = selectedClass;
  });

  let classFilter = $state('');
  let allClassFilter = $state('');

  let diffViewMode = $state<'inline' | 'split'>(localStorage.getItem('diff_view_mode') === 'split' ? 'split' : 'inline');
  let diffExpand = $state<'hunks' | 'full'>(localStorage.getItem('diff_expand') === 'full' ? 'full' : 'hunks');

  // Source pane: 'none' | 'class' (snapshot / per-class diff) | 'summary' (version diff)
  let sourceMode = $state<'none' | 'class' | 'summary'>('none');
  let snapshot = $state<SnapshotPayload | null>(null);
  let snapshotError = $state(false);
  let classDiff = $state<DiffPayload | null>(null);
  let diffOptions = $state<DiffOption[]>([]);
  let diffOptionIdx = $state(0);
  let summary = $state<VersionDiffPayload | null>(null);
  let summaryTarget = $state('live');
  let summaryBase = $state('none');
  let summaryError = $state<string | null>(null);
  let summaryLoading = $state(false);
  let summaryDiffs = $state<Record<string, DiffPayload | null>>({});
  let scrollToClass = $state<string | null>(null);

  let selectSeq = 0;
  let loadSeq = 0;

  const byKind = (list: CodeClassState[]) =>
    codeUi.kindFilter === 'all' ? list : list.filter((c) => (c.object_type ?? '').toLowerCase() === codeUi.kindFilter);

  const byName = (list: CodeClassState[], filter: string) => {
    const f = filter.toLowerCase();
    return f ? list.filter((c) => c.class_name.toLowerCase().includes(f)) : list;
  };

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
          const liveCheck = await codeApi.versionDiff({ base_version_id: versions[0].version_id, target_version_id: 'live' });
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
    } catch {
      versionsLoading = false;
      toast('Could not load code versions');
    }
  }

  async function ensureAllClasses(): Promise<CodeClassState[]> {
    if (!allClasses.length && versions.length) allClasses = await codeApi.versionClasses(versions[0].version_id);
    return allClasses;
  }

  function resetSource() {
    selectedClass = null;
    summary = null;
    summaryError = null;
    classDiff = null;
    snapshot = null;
    diffOptions = [];
  }

  // ---------------------------------------------------------------------------
  // Version selection
  // ---------------------------------------------------------------------------

  async function selectVersion(versionId: string) {
    const mySeq = ++selectSeq;
    selectedVersion = versionId;
    resetSource();
    const meta = versions.find((v) => v.version_id === versionId);
    try {
      const classes = await codeApi.versionClasses(versionId);
      if (mySeq !== selectSeq) return;
      versionClasses = classes;
    } catch {
      toast('Could not load version');
      return;
    }
    // Versions with changed classes show a diff overview instead of auto-selecting a class.
    if (meta?.changed_class_names?.length) {
      await showVersionDiff(versionId, null);
      return;
    }
    if (versionClasses.length) await selectClass(versionClasses[0]);
  }

  async function selectLiveVersion() {
    selectedVersion = 'live';
    resetSource();
    if (versions.length) {
      try {
        versionClasses = await codeApi.versionClasses(versions[0].version_id);
      } catch {
        toast('Could not load classes');
      }
    }
    await showVersionDiff('live', versions[0]?.version_id ?? null);
  }

  async function showVersionDiff(target: string, base: string | null, focusClass: string | null = null) {
    const mySeq = ++selectSeq;
    const targetIdx = target === 'live' ? -1 : versions.findIndex((v) => v.version_id === target);
    const defaultBase =
      target === 'live' ? (versions[0]?.version_id ?? 'none') : (versions[targetIdx + 1]?.version_id ?? 'none');
    const baseId = base ?? defaultBase;
    resetSource();
    summaryDiffs = {};
    summaryLoading = true;
    summaryTarget = target;
    summaryBase = baseId;
    scrollToClass = focusClass;
    sourceMode = 'summary';
    try {
      const result = await codeApi.versionDiff({ base_version_id: baseId, target_version_id: target });
      if (mySeq !== selectSeq) return;
      summaryLoading = false;
      if (result.error) {
        summaryError = result.message ?? result.error;
        return;
      }
      summary = result;
      summaryBase = result.base_version_id ?? baseId;
    } catch {
      if (mySeq !== selectSeq) return;
      summaryLoading = false;
      summaryError = 'Could not load diff.';
    }
  }

  // ---------------------------------------------------------------------------
  // Class selection (source snapshot)
  // ---------------------------------------------------------------------------

  async function selectClass(entry: CodeClassState) {
    const mySeq = ++selectSeq;
    resetSource();
    selectedClass = entry.class_name;
    snapshotError = false;
    diffOptionIdx = 0;
    sourceMode = 'class';
    const [snap, opts] = await Promise.all([
      codeApi.snapshot(entry.source_hash).catch(() => null),
      buildDiffOptions(entry),
    ]);
    if (mySeq !== selectSeq) return;
    diffOptions = opts;
    if (snap) snapshot = snap;
    else {
      snapshotError = true;
      toast('Source unavailable');
    }
    queueMicrotask(() =>
      document
        .querySelector(`.code-class-item.active`)
        ?.scrollIntoView({ block: 'nearest' }),
    );
  }

  async function buildDiffOptions(entry: CodeClassState): Promise<DiffOption[]> {
    const opts: DiffOption[] = [];
    const isLive = selectedVersion === 'live';
    const effectiveIdx = isLive ? 0 : versions.findIndex((v) => v.version_id === selectedVersion);
    const prevVersion = effectiveIdx >= 0 ? (versions[effectiveIdx + 1] ?? null) : null;
    const isViewingCurrent = isLive || (versions.length > 0 && selectedVersion === versions[0].version_id);

    if (prevVersion) {
      try {
        const match = (await codeApi.versionClasses(prevVersion.version_id)).find((c) => c.class_name === entry.class_name);
        if (match && match.source_hash !== entry.source_hash) {
          opts.push({ label: prevVersion.label, hash_old: match.source_hash, hash_new: entry.source_hash });
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
    // Newest version: offer Live when the in-memory source diverged from disk.
    if (isViewingCurrent && hasLiveClasses && liveChanges) {
      const ch = liveChanges.find((c) => c.class_name === entry.class_name && c.status === 'changed' && c.hash_new);
      if (ch && ch.hash_new !== entry.source_hash) {
        opts.push({ label: 'Live', hash_old: entry.source_hash, hash_new: ch.hash_new as string });
      }
    }
    return opts;
  }

  function onClassClick(entry: CodeClassState) {
    if (entry.class_name === selectedClass) {
      // Deselect — back to the version change summary when the version has changes.
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
  // Per-class diff mode
  // ---------------------------------------------------------------------------

  async function enterDiffMode() {
    if (classDiff) return;
    if (!diffOptions.length) {
      toast('No previous version to diff against');
      return;
    }
    diffOptionIdx = 0;
    await loadClassDiff(diffOptions[0]);
  }

  async function loadClassDiff(opt: DiffOption) {
    const mySeq = ++selectSeq;
    try {
      const data = await codeApi.diff(opt.hash_old, opt.hash_new, true);
      if (mySeq === selectSeq) classDiff = data;
    } catch {
      toast('Diff unavailable');
    }
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
      selectedVersion = relevant[0].version_id;
      try {
        versionClasses = await codeApi.versionClasses(relevant[0].version_id);
        const match = versionClasses.find((c) => c.class_name === entry.class_name);
        if (match) {
          await selectClass(match);
          return;
        }
      } catch {
        toast('Could not load version');
      }
    }
    await selectClass(entry);
  }

  async function selectVersionForClass(versionId: string, className: string) {
    selectedVersion = versionId;
    try {
      versionClasses = await codeApi.versionClasses(versionId);
      const match = versionClasses.find((c) => c.class_name === className);
      if (match) await selectClass(match);
    } catch {
      toast('Could not load version');
    }
  }

  async function applyBrowseMode() {
    if (codeUi.browseMode === 'version') {
      const target = selectedVersion ?? versions[0]?.version_id ?? null;
      if (target === 'live') await selectLiveVersion();
      else if (target) await selectVersion(target);
    } else {
      try {
        await ensureAllClasses();
      } catch {
        toast('Could not load classes');
      }
      if (selectedClass) return;
      if (allClasses.length) await selectClassFirst(allClasses[0]);
    }
  }

  // ---------------------------------------------------------------------------
  // Cross-view navigation targets (detail pane Source / Show diff, popups)
  // ---------------------------------------------------------------------------

  async function selectCodeTarget(className: string, depHash: string | null, sourceHash: string | null) {
    codeUi.browseMode = 'version';
    let versionId: string | null = versions[0]?.version_id ?? null;
    let resolvedHash = sourceHash;
    try {
      if (depHash) {
        const res = await codeApi.resolveDepHash(depHash, className);
        versionId = res.version_id ?? versionId;
        resolvedHash = res.source_hash;
      } else if (sourceHash) {
        versionId = (await codeApi.sourceHashVersion(sourceHash)).version_id ?? versionId;
      }
    } catch {
      /* fall back to the newest version */
    }
    if (!versionId) return;
    const mySeq = ++selectSeq;
    selectedVersion = versionId;
    resetSource();
    const classes = await codeApi.versionClasses(versionId).catch(() => null);
    if (mySeq !== selectSeq) return;
    if (!classes) {
      toast('Could not load version');
      return;
    }
    versionClasses = classes;
    const match =
      (resolvedHash ? classes.find((c) => c.source_hash === resolvedHash) : null) ??
      classes.find((c) => c.class_name === className);
    if (match) await selectClass(match);
  }

  async function selectDiffRecord(recordId: string, className: string | null) {
    try {
      const data = await codeApi.versionDiff({ record_id: recordId });
      if (data.error) {
        resetSource();
        sourceMode = 'summary';
        summaryLoading = false;
        summaryError = data.message ?? 'Snapshot not available for this entry';
        return;
      }
      const baseVersionId = data.base_version_id ?? null;
      hasLiveStale = !!data.has_live_stale;
      // Always diff against live so a stale entry shows what actually changed.
      selectedVersion = hasLiveClasses ? 'live' : (versions[0]?.version_id ?? 'live');
      const baseMeta = versions.find((v) => v.version_id === baseVersionId) ?? versions[0];
      if (baseMeta) {
        try {
          versionClasses = await codeApi.versionClasses(baseMeta.version_id);
        } catch {
          /* keep current classes */
        }
      }
      await showVersionDiff('live', baseVersionId, className);
    } catch {
      toast('Could not load diff');
    }
  }

  async function findInEntries() {
    if (!selectedClass) return;
    if (selectedVersion && selectedVersion !== 'live') filterState.versionFilter = selectedVersion;
    await navigateToClass(selectedClass);
  }

  // ---------------------------------------------------------------------------
  // Derived view state
  // ---------------------------------------------------------------------------

  const visibleVersions = $derived(codeUi.hideEmpty ? versions.filter((v) => v.has_entries) : versions);
  const visibleVersionClasses = $derived(byName(byKind(versionClasses), classFilter));
  const visibleAllClasses = $derived(byName(byKind(allClasses), allClassFilter));
  const versionsForClass = $derived(
    selectedClass ? versions.filter((v) => (v.class_names ?? []).includes(selectedClass as string)) : [],
  );

  const inSummary = $derived(sourceMode === 'summary');
  const showDiffBar = $derived((sourceMode === 'class' && diffOptions.length > 0) || (inSummary && !!summary?.changes?.length));
  const diffActive = $derived(classDiff !== null || inSummary);
  const anySummaryFull = $derived(Object.values(summaryDiffs).some((d) => !!d?.full_old));
  const canExpand = $derived(classDiff ? !!classDiff.full_old : inSummary && anySummaryFull);

  const title = $derived.by(() => {
    if (sourceMode === 'class') return selectedClass ?? '';
    if (inSummary) return summaryTarget === 'live' ? 'Live' : (versions.find((v) => v.version_id === summaryTarget)?.label ?? '');
    return '';
  });

  const baseOptions = $derived([
    ...(hasLiveClasses ? [{ value: 'live', label: 'Live' }] : []),
    ...versions.map((v) => ({ value: v.version_id, label: v.label })),
    { value: 'none', label: '(empty)' },
  ]);

  // ---------------------------------------------------------------------------
  // Wiring
  // ---------------------------------------------------------------------------

  let started = false;

  $effect(() => {
    void load();
  });

  // Once versions are in: handle a pending navigation target, else the browse mode default.
  $effect(() => {
    if (versionsLoading) return;
    const target = codeNav.target;
    const diffId = codeNav.diffRecordId;
    const versionId = codeNav.versionId;
    untrack(() => {
      if (versionId) {
        codeNav.versionId = null;
        started = true;
        void selectVersion(versionId);
      } else if (target) {
        codeNav.target = null;
        started = true;
        void selectCodeTarget(target.className, target.depHash ?? null, target.sourceHash ?? null);
      } else if (diffId) {
        codeNav.diffRecordId = null;
        started = true;
        void selectDiffRecord(diffId, codeNav.diffClassName);
      } else if (!started) {
        started = true;
        void applyBrowseMode();
      }
    });
  });

  // Top-bar browse-mode switch.
  let lastMode = codeUi.browseMode;
  $effect(() => {
    const mode = codeUi.browseMode;
    if (mode === lastMode) return;
    lastMode = mode;
    localStorage.setItem('code_browse_mode', mode);
    if (!versionsLoading) untrack(() => void applyBrowseMode());
  });

  function onKeydown(e: KeyboardEvent) {
    const t = e.target as HTMLElement;
    if (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT') return;
    if (e.metaKey || (e.key !== 'ArrowDown' && e.key !== 'ArrowUp')) return;
    e.preventDefault();
    const byClass = codeUi.browseMode === 'class';
    const list = byClass ? visibleAllClasses : visibleVersionClasses;
    if (!list.length) return;
    const cur = list.findIndex((c) => c.class_name === selectedClass);
    const next =
      e.key === 'ArrowDown'
        ? cur === -1
          ? 0
          : Math.min(cur + 1, list.length - 1)
        : cur === -1
          ? list.length - 1
          : Math.max(cur - 1, 0);
    if (byClass) void selectClassFirst(list[next]);
    else void selectClass(list[next]);
  }
</script>

<svelte:window onkeydown={onKeydown} />

{#snippet classItem(c: CodeClassState, onclick: () => void)}
  <div class="code-class-item" class:active={c.class_name === selectedClass} role="button" tabindex="-1" {onclick} onkeydown={(e) => e.key === 'Enter' && onclick()}>
    <span class="code-class-name"
      >{c.class_name}{#if c.is_stale}<span class="stale-dot" title="Source changed since this version"></span>{/if}</span
    >
    <span class="code-class-meta"><TypeBadge type={c.object_type} /></span>
  </div>
{/snippet}

{#snippet versionItem(id: string, label: string, active: boolean, onclick: () => void, stale = false)}
  <div class="code-version-item" class:active data-version-id={id} role="button" tabindex="-1" {onclick} onkeydown={(e) => e.key === 'Enter' && onclick()}>
    {label}{#if stale}&nbsp;<span class="stale-dot" title="In-memory code differs from disk"></span>{/if}
  </div>
{/snippet}

<div class="view-code">
  <div class="code-pane code-pane--versions" style:flex={layout.widths.codeVersions ? `0 0 ${layout.widths.codeVersions}px` : null}>
    <Resizer pane="codeVersions" edge="right" min={200} max={() => window.innerWidth * 0.35} />
    <div class="code-pane-filter-row">
      {#if codeUi.browseMode === 'class'}
        <input class="code-filter" placeholder="Filter classes…" bind:value={allClassFilter} />
      {/if}
    </div>
    <div class="code-version-list">
      {#if versionsLoading}
        <div class="detail-empty">Loading…</div>
      {:else if codeUi.browseMode === 'version'}
        {#if visibleVersions.length === 0}
          <div class="detail-empty">
            {#if codeUi.hideEmpty && versions.length}
              All versions are empty. <a href="#top" onclick={(e) => (e.preventDefault(), (codeUi.hideEmpty = false))}>Show all</a>
            {:else}
              No code snapshots found.
            {/if}
          </div>
        {:else}
          {#if hasLiveClasses}
            {@render versionItem('live', 'Live', selectedVersion === 'live', () => void selectLiveVersion(), hasLiveStale)}
          {/if}
          {#each visibleVersions as v (v.version_id)}
            {@render versionItem(v.version_id, v.label, v.version_id === selectedVersion, () => void selectVersion(v.version_id))}
          {/each}
        {/if}
      {:else if visibleAllClasses.length === 0}
        <div class="detail-empty">No classes.</div>
      {:else}
        {#each visibleAllClasses as c (c.class_name)}
          {@render classItem(c, () => void selectClassFirst(c))}
        {/each}
      {/if}
    </div>
  </div>

  <div class="code-pane code-pane--classes" style:flex={layout.widths.codeClasses ? `0 0 ${layout.widths.codeClasses}px` : null}>
    <Resizer pane="codeClasses" edge="right" min={200} max={() => window.innerWidth * 0.4} />
    <div class="code-pane-filter-row">
      {#if codeUi.browseMode === 'version'}
        <input class="code-filter" placeholder="Filter…" bind:value={classFilter} />
      {/if}
    </div>
    <div class="code-class-list">
      {#if codeUi.browseMode === 'version'}
        {#if visibleVersionClasses.length === 0}
          <div class="detail-empty">No classes.</div>
        {/if}
        {#each visibleVersionClasses as c (c.class_name)}
          {@render classItem(c, () => onClassClick(c))}
        {/each}
      {:else if selectedClass && versionsForClass.length === 0}
        <div class="detail-empty">No snapshots for this class.</div>
      {:else}
        {#each versionsForClass as v (v.version_id)}
          {@render versionItem(v.version_id, v.label, v.version_id === selectedVersion, () =>
            void selectVersionForClass(v.version_id, selectedClass as string),
          )}
        {/each}
      {/if}
    </div>
  </div>

  <div class="code-pane code-pane--source">
    <ReloadBar />
    <div class="code-source-actions">
      <span class="pane-title">{title}</span>
      <span class="main-hd-spacer"></span>
      {#if sourceMode === 'class' && selectedClass}
        <button class="act-btn" onclick={() => void findInEntries()}>Find entries</button>
      {/if}
    </div>
    {#if showDiffBar}
      <div class="code-diff-bar">
        {#if !inSummary}
          <div class="kind-group">
            <button class="kind-tab" class:active={!classDiff} onclick={() => (classDiff = null)}>Source</button>
            <button class="kind-tab" class:active={!!classDiff} onclick={() => void enterDiffMode()}>Diff</button>
          </div>
        {/if}
        <div class="kind-group" class:seg-disabled={!diffActive}>
          <button class="kind-tab" class:active={diffViewMode === 'inline'} onclick={() => setDiffViewMode('inline')}>Inline</button>
          <button class="kind-tab" class:active={diffViewMode === 'split'} onclick={() => setDiffViewMode('split')}>Side by side</button>
        </div>
        <div class="kind-group" class:seg-disabled={!canExpand}>
          <button class="kind-tab" class:active={diffExpand === 'hunks'} onclick={() => setDiffExpand('hunks')}>Hunks</button>
          <button class="kind-tab" class:active={diffExpand === 'full'} onclick={() => setDiffExpand('full')}>Full</button>
        </div>
      </div>
    {/if}
    <div class="code-source-panel">
      {#if sourceMode === 'summary'}
        {#if summaryLoading}
          <div class="diff-loading">Loading…</div>
        {:else if summaryError}
          <div class="diff-no-snapshot">{summaryError}</div>
        {:else}
          <div class="diff-version-header">
            <span class="diff-version-label">Compare with</span>
            <select
              class="diff-version-select"
              value={summaryBase}
              onchange={(e) => void showVersionDiff(summaryTarget, e.currentTarget.value)}
            >
              {#each baseOptions as o (o.value)}<option value={o.value}>{o.label}</option>{/each}
            </select>
          </div>
          {#if !summary?.changes?.length}
            <div class="diff-no-snapshot">No changes between these versions.</div>
          {:else}
            <ChangeSummary
              changes={summary.changes}
              mode={diffViewMode}
              expand={diffExpand}
              {scrollToClass}
              onLink={onSourceLink}
              onDiff={(cls, d) => (summaryDiffs[cls] = d)}
            />
          {/if}
        {/if}
      {:else if classDiff}
        {#if diffOptions.length}
          <div class="diff-version-header">
            <span class="diff-version-label">Compare with</span>
            <select
              class="diff-version-select"
              value={String(diffOptionIdx)}
              onchange={(e) => {
                diffOptionIdx = Number(e.currentTarget.value);
                void loadClassDiff(diffOptions[diffOptionIdx]);
              }}
            >
              {#each diffOptions as o, i (i)}<option value={String(i)}>{o.label}</option>{/each}
            </select>
          </div>
        {/if}
        <DiffTable diff={classDiff} mode={diffViewMode} expand={diffExpand} />
      {:else if snapshot}
        <SnapshotTable {snapshot} onLink={onSourceLink} />
      {:else if snapshotError}
        <div class="diff-no-snapshot">Source unavailable</div>
      {/if}
    </div>
  </div>
</div>
