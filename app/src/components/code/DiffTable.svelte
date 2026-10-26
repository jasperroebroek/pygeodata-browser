<script lang="ts">
  import type { DiffHunk, DiffPayload, DiffSegment } from '../../lib/apiCode';

  let {
    diff,
    mode = 'inline',
    expand = 'hunks',
  }: {
    diff: DiffPayload;
    mode?: 'inline' | 'split';
    expand?: 'hunks' | 'full';
  } = $props();

  type Row =
    | { t: 'hunk'; header: string }
    | {
        t: 'ctx' | 'del' | 'add';
        lo: number | null;
        ln: number | null;
        sign: ' ' | '−' | '+';
        text: string;
        oldText: string | null;
        segments: DiffSegment[] | null;
      };

  function hunkRows(hunk: DiffHunk): Row[] {
    return hunk.lines.map((line) => {
      if (line.type === 'ctx') {
        return {
          t: 'ctx' as const,
          lo: line.line_old,
          ln: line.line_new,
          sign: ' ' as const,
          text: line.text,
          oldText: line.text,
          segments: null,
        };
      }
      if (line.type === 'del') {
        return {
          t: 'del' as const,
          lo: line.line_old,
          ln: null,
          sign: '−' as const,
          text: line.text,
          oldText: line.text,
          segments: line.segments ?? null,
        };
      }
      return {
        t: 'add' as const,
        lo: null,
        ln: line.line_new,
        sign: '+' as const,
        text: line.text,
        oldText: null,
        segments: line.segments ?? null,
      };
    });
  }

  const rows = $derived.by(() => {
    const hunks = diff.hunks ?? [];
    if (!hunks.length) return [] as Row[];

    if (expand === 'full' && diff.full_old && diff.full_new) {
      const linesOld = diff.full_old.split('\n');
      const linesNew = diff.full_new.split('\n');
      if (linesOld[linesOld.length - 1] === '') linesOld.pop();
      if (linesNew[linesNew.length - 1] === '') linesNew.pop();

      const ctxRow = (lo: number, ln: number): Row => ({
        t: 'ctx',
        lo,
        ln,
        sign: ' ',
        text: linesNew[ln - 1] ?? '',
        oldText: linesOld[lo - 1] ?? '',
        segments: null,
      });

      const out: Row[] = [];
      let curOld = 1;
      let curNew = 1;
      for (const hunk of hunks) {
        while (curOld < hunk.start_old && curNew < hunk.start_new) out.push(ctxRow(curOld++, curNew++));
        while (curOld < hunk.start_old) out.push(ctxRow(curOld++, curNew));
        while (curNew < hunk.start_new) out.push(ctxRow(curOld, curNew++));
        out.push(...hunkRows(hunk));
        for (const line of hunk.lines) {
          if (line.line_old !== null) curOld = line.line_old + 1;
          if (line.line_new !== null) curNew = line.line_new + 1;
        }
      }
      while (curOld <= linesOld.length && curNew <= linesNew.length) out.push(ctxRow(curOld++, curNew++));
      return out;
    }

    const out: Row[] = [];
    for (const hunk of hunks) {
      out.push({ t: 'hunk', header: hunk.header });
      out.push(...hunkRows(hunk));
    }
    return out;
  });

</script>

{#if !rows.length}
  <div class="identical">Files are identical — no changes.</div>
{:else if mode === 'split'}
  <table class="diff diff--split">
    <colgroup><col class="ln-col" /><col /><col class="ln-col" /><col /></colgroup>
    <tbody>
      {#each rows as row}
        {#if row.t === 'hunk'}
          <tr class="hunk-hdr"><td colspan="4">{row.header}</td></tr>
        {:else if row.t === 'del'}
          <tr class="del">
            <td class="ln">{row.lo ?? ''}</td>
            <td class="code">
              {#each row.segments ?? [] as s}
                {#if s.type === 'eq'}{s.text}{:else if s.type === 'del'}<span class="wd wd--del">{s.text}</span>{/if}
              {/each}{row.segments ? '' : row.text}
            </td>
            <td class="ln empty"></td>
            <td class="code empty"></td>
          </tr>
        {:else if row.t === 'add'}
          <tr class="add">
            <td class="ln empty"></td>
            <td class="code empty"></td>
            <td class="ln">{row.ln ?? ''}</td>
            <td class="code">
              {#each row.segments ?? [] as s}
                {#if s.type === 'eq'}{s.text}{:else if s.type === 'ins'}<span class="wd wd--ins">{s.text}</span>{/if}
              {/each}{row.segments ? '' : row.text}
            </td>
          </tr>
        {:else}
          <tr class="ctx">
            <td class="ln">{row.lo ?? ''}</td>
            <td class="code">{row.oldText ?? row.text}</td>
            <td class="ln">{row.ln ?? ''}</td>
            <td class="code">{row.text}</td>
          </tr>
        {/if}
      {/each}
    </tbody>
  </table>
{:else}
  <table class="diff diff--inline">
    <tbody>
      {#each rows as row}
        {#if row.t === 'hunk'}
          <tr class="hunk-hdr"><td colspan="4">{row.header}</td></tr>
        {:else}
          <tr class={row.t}>
            <td class="ln">{row.lo ?? ''}</td>
            <td class="ln">{row.ln ?? ''}</td>
            <td class="sign">{row.sign}</td>
            <td class="code">
              {#each row.segments ?? [] as s}
                {#if s.type === 'eq'}{s.text}{:else if row.t === 'del' && s.type === 'del'}<span class="wd wd--del">{s.text}</span>{:else if row.t === 'add' && s.type === 'ins'}<span class="wd wd--ins">{s.text}</span>{/if}
              {/each}{row.segments ? '' : row.text}
            </td>
          </tr>
        {/if}
      {/each}
    </tbody>
  </table>
{/if}

<style>
  .diff {
    width: 100%;
    border-collapse: collapse;
    font-family: var(--font-mono);
    font-size: var(--fs-xs);
    line-height: 1.6;
    table-layout: fixed;
  }

  .ln-col {
    width: 44px;
  }

  td {
    padding: 0 8px;
    vertical-align: top;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }

  .ln {
    color: var(--text-3);
    text-align: right;
    user-select: none;
    font-size: var(--fs-xs);
  }

  .sign {
    color: var(--text-3);
    user-select: none;
    width: 16px;
  }

  .code {
    color: var(--text);
  }

  .ctx .code {
    color: var(--text-2);
  }

  .del .code,
  .del .sign {
    background: color-mix(in srgb, var(--danger) 7%, transparent);
  }

  .del .sign {
    color: var(--danger);
    font-weight: 600;
  }

  .add .code,
  .add .sign {
    background: color-mix(in srgb, var(--success) 7%, transparent);
  }

  .add .sign {
    color: var(--success);
    font-weight: 600;
  }

  .wd--del {
    background: color-mix(in srgb, var(--danger) 20%, transparent);
    color: var(--danger);
    border-radius: 2px;
  }

  .wd--ins {
    background: color-mix(in srgb, var(--success) 20%, transparent);
    color: var(--success);
    border-radius: 2px;
  }

  .hunk-hdr td {
    background: var(--code-bg);
    color: var(--text-3);
    font-size: var(--fs-xs);
    padding-top: 2px;
    padding-bottom: 2px;
  }

  .empty {
    background: color-mix(in srgb, var(--bg) 55%, transparent);
  }

  .identical {
    padding: var(--s-3);
    color: var(--text-3);
    font-size: var(--fs-sm);
  }
</style>
