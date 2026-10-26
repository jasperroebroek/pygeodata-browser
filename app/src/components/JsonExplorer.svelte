<script lang="ts" module>
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
</script>

<script lang="ts">
  import JsonExplorer from './JsonExplorer.svelte';

  type Obj = Record<string, unknown>;

  let {
    data,
    depth = 0,
    filterHidden = true,
    knownClasses = null,
    onClass,
  }: {
    data: unknown;
    depth?: number;
    filterHidden?: boolean;
    knownClasses?: Set<string> | null;
    onClass: (cls: string) => void;
  } = $props();

  let collapsed = $state<Record<string, boolean>>({});

  const entries = $derived.by((): [string, unknown][] => {
    if (Array.isArray(data)) return data.map((v, i) => [String(i), v]);
    if (data !== null && typeof data === 'object') {
      const all = Object.entries(data as Obj);
      return filterHidden && depth === 0 ? all.filter(([k]) => !HIDDEN_JSON_KEYS.has(k)) : all;
    }
    return [];
  });

  const isObj = (v: unknown): v is Obj => v !== null && typeof v === 'object' && !Array.isArray(v);
  const isDataRef = (v: unknown): v is Obj => isObj(v) && !!v.class_name && !!v.params;

  /** Child keys of a plain object: hidden keys (when filtering) and its own class_name drop out. */
  function childKeys(v: Obj): string[] {
    const cn = v.class_name;
    return Object.keys(v).filter((k) => !(filterHidden && HIDDEN_JSON_KEYS.has(k)) && !(cn && k === 'class_name'));
  }

  function pick(v: Obj, keys: string[]): Obj {
    return Object.fromEntries(keys.map((k) => [k, v[k]]));
  }

  function link(e: MouseEvent, cls: string) {
    e.preventDefault();
    onClass(cls);
  }
</script>

{#snippet keyEl(key: string)}
  {#if knownClasses?.has(key)}
    <a href="#top" class="jx-key jx-cls" onclick={(e) => link(e, key)}>{key}</a>
  {:else}
    <span class="jx-key">{key}</span>
  {/if}
{/snippet}

{#snippet toggle(key: string, hasChildren: boolean)}
  {#if hasChildren}
    <button
      class="jx-toggle"
      class:jx-open={!collapsed[key]}
      aria-label={collapsed[key] ? 'expand' : 'collapse'}
      onclick={() => (collapsed[key] = !collapsed[key])}
    ></button>
  {:else}
    <span class="jx-leaf-dot"></span>
  {/if}
{/snippet}

<ul class="jx-list jx-depth-{depth}">
  {#each entries as [key, value] (key)}
    <li class="jx-item">
      {#if isDataRef(value)}
        {@const inner = (value.params ?? {}) as Obj}
        {@const has = Object.keys(inner).length > 0}
        <span class="jx-row">
          {@render toggle(key, has)}
          {@render keyEl(key)}
          <span class="jx-sep">→</span>
          <a href="#top" class="jx-cls" onclick={(e) => link(e, String(value.class_name))}>{value.class_name}</a>
        </span>
        {#if has && !collapsed[key]}
          <JsonExplorer data={inner} depth={depth + 1} {filterHidden} {knownClasses} {onClass} />
        {/if}
      {:else if Array.isArray(value)}
        <span class="jx-row">
          {@render toggle(key, value.length > 0)}
          {@render keyEl(key)}
          <span class="jx-dim">[{value.length}]</span>
        </span>
        {#if value.length && !collapsed[key]}
          <JsonExplorer data={value} depth={depth + 1} {filterHidden} {knownClasses} {onClass} />
        {/if}
      {:else if isObj(value)}
        {@const cn = value.class_name ? String(value.class_name) : null}
        {@const keys = childKeys(value)}
        <span class="jx-row">
          {@render toggle(key, keys.length > 0)}
          {#if cn && cn === key}
            <a href="#top" class="jx-key jx-cls" onclick={(e) => link(e, cn)}>{key}</a>
          {:else}
            {@render keyEl(key)}
          {/if}
          {#if cn && cn !== key}
            <a href="#top" class="jx-cls" onclick={(e) => link(e, cn)}>{cn}</a>
          {/if}
        </span>
        {#if keys.length && !collapsed[key]}
          <JsonExplorer data={pick(value, keys)} depth={depth + 1} {filterHidden} {knownClasses} {onClass} />
        {/if}
      {:else}
        <span class="jx-row">
          <span class="jx-leaf-dot"></span>
          {@render keyEl(key)}
          <span class="jx-sep">:</span>
          <span class="jx-val">{value === null ? 'null' : String(value)}</span>
        </span>
      {/if}
    </li>
  {/each}
</ul>
