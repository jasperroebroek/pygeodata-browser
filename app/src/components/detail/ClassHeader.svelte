<script lang="ts">
  import type { DetailPayload } from '../../lib/api';
  import { navigateToCodeClass } from '../../lib/nav.svelte';
  import { selectClasses } from '../../lib/stores.svelte';
  import { formatMtime } from './apiDetail';

  let {
    detail,
    onClassJson = null,
    onGraph = null,
  }: {
    detail: DetailPayload;
    onClassJson?: ((path: string, cls: string, kind: 'tree' | 'nodes' | 'registry') => void) | null;
    onGraph?: ((path: string, cls: string) => void) | null;
  } = $props();

  const kindClass: Record<string, string> = {
    Data: 'kind-badge--data',
    Figure: 'kind-badge--figure',
    Table: 'kind-badge--table',
  };

  function jump(cls: string): void {
    selectClasses([cls]);
  }

  // code_versions is oldest-first; pin the newest snapshot of the class.
  function newestSourceHash(): string | undefined {
    const versions = detail.code_versions;
    return versions.length ? versions[versions.length - 1].source_hash : undefined;
  }

  function openCodeView(): void {
    navigateToCodeClass(detail.class_name, newestSourceHash());
  }
</script>

<div class="dcard">
  <div class="dcard-hd">
    <div class="dcard-hd-top">
      <span class="dcard-hd-label">Class</span>
      <span class="dcard-hd-title">
        <button class="cls-name" title="Open in code view" onclick={openCodeView}>
          {detail.class_name}
        </button>
        {#if detail.object_type}
          <span class="kind-badge {kindClass[detail.object_type] ?? ''}">
            {detail.object_type}
          </span>
        {/if}
        {#if !detail.loaded}
          <span
            class="dbadge dbadge--cache"
            title="Not loaded in Python registry — data comes from the catalog snapshot"
          >
            cache-only
          </span>
        {/if}
        {#if detail.source_stale}
          <span class="dbadge dbadge--warn" title="Source code changed since the last run">
            stale
          </span>
        {/if}
        {#if !detail.source_stale && detail.deps_stale}
          <span class="dbadge dbadge--warn" title="An upstream dependency changed since the last run">
            stale
          </span>
        {/if}
      </span>
    </div>
    {#if detail.source_available || onClassJson || onGraph}
      <div class="dcard-hd-actions">
        {#if detail.source_available}
          <button
            class="act-btn"
            title="View source code for this class"
            onclick={openCodeView}
          >
            Source
          </button>
        {/if}
        {#if detail.graph_available && detail.class_graph_path && onGraph}
          <button
            class="act-btn"
            title="Open the dependency graph for this class"
            onclick={() => onGraph?.(detail.class_graph_path ?? '', detail.class_name)}
          >
            Graph
          </button>
        {/if}
        {#if detail.class_tree_path && onClassJson}
          <button
            class="act-btn"
            title="View dependency tree JSON"
            onclick={() => onClassJson?.(detail.class_tree_path ?? '', detail.class_name, 'tree')}
          >
            Tree
          </button>
          <button
            class="act-btn"
            title="View nodes JSON"
            onclick={() => onClassJson?.(detail.class_tree_path ?? '', detail.class_name, 'nodes')}
          >
            Nodes
          </button>
        {/if}
        {#if detail.class_registry_path && onClassJson}
          <button
            class="act-btn"
            title="View registry JSON"
            onclick={() => onClassJson?.(detail.class_registry_path ?? '', detail.class_name, 'registry')}
          >
            Registry
          </button>
        {/if}
      </div>
    {/if}
  </div>
  <div class="dcard-body">
    <div class="dep-block">
      <span class="spec-kv-label">Call dependencies</span>
      <div class="dep-chips">
        {#if detail.call_dependency_names.length === 0}
          <span class="dep-nil">None</span>
        {:else}
          {#each detail.call_dependency_names as name (name)}
            <button class="dep-chip" onclick={() => jump(name)}>{name}</button>
          {/each}
        {/if}
      </div>
    </div>
    <div class="dep-block">
      <span class="spec-kv-label">Inheritance dependencies</span>
      <div class="dep-chips">
        {#if detail.inheritance_dependency_names.length === 0}
          <span class="dep-nil">None</span>
        {:else}
          {#each detail.inheritance_dependency_names as name (name)}
            <button class="dep-chip" onclick={() => jump(name)}>{name}</button>
          {/each}
        {/if}
      </div>
    </div>
    {#if detail.code_versions.length > 0}
      <div class="ver-history">
        {#each detail.code_versions.slice().reverse() as v, i (v.source_hash)}
          {@const isCurrent = i === 0}
          <div class="ver-history-row" class:ver-history-row--current={isCurrent}>
            <span class="ver-dot" class:ver-dot--change={v.is_version_change}></span>
            <span class="mono">{v.source_hash.slice(0, 8)}</span>
            <span>{formatMtime(v.mtime)}</span>
            {#if v.is_version_change}
              <span class="dbadge dbadge--warn">version change</span>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
    {#if detail.entry_version_label}
      <div class="dep-block">
        <span class="spec-kv-label">Entry version</span>
        <span class="dbadge dbadge--neutral">{detail.entry_version_label}</span>
      </div>
    {/if}
  </div>
</div>

<style>
  .cls-name {
    background: none;
    border: none;
    padding: 0;
    font: inherit;
    font-weight: inherit;
    color: var(--link);
    cursor: pointer;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .cls-name:hover {
    text-decoration: underline;
  }
</style>
