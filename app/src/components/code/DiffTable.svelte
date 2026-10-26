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
    | { t: 'ctx'; lo: number; ln: number; oldText: string; text: string }
    | { t: 'del'; lo: number | null; text: string; segments: DiffSegment[] | null }
    | { t: 'add'; ln: number | null; text: string; segments: DiffSegment[] | null };

  function hunkRows(hunk: DiffHunk): Row[] {
    return hunk.lines.map((line): Row => {
      if (line.type === 'ctx') {
        return { t: 'ctx', lo: line.line_old ?? 0, ln: line.line_new ?? 0, oldText: line.text, text: line.text };
      }
      if (line.type === 'del') return { t: 'del', lo: line.line_old, text: line.text, segments: line.segments ?? null };
      return { t: 'add', ln: line.line_new, text: line.text, segments: line.segments ?? null };
    });
  }

  const rows = $derived.by((): Row[] => {
    const hunks = diff.hunks ?? [];
    if (!hunks.length) return [];
    if (expand === 'full' && diff.full_old && diff.full_new) {
      const linesOld = diff.full_old.split('\n');
      const linesNew = diff.full_new.split('\n');
      if (linesOld[linesOld.length - 1] === '') linesOld.pop();
      if (linesNew[linesNew.length - 1] === '') linesNew.pop();
      const ctx = (lo: number, ln: number): Row => ({
        t: 'ctx',
        lo,
        ln,
        oldText: linesOld[lo - 1] ?? '',
        text: linesNew[ln - 1] ?? '',
      });
      const out: Row[] = [];
      let curOld = 1;
      let curNew = 1;
      for (const hunk of hunks) {
        while (curOld < hunk.start_old && curNew < hunk.start_new) out.push(ctx(curOld++, curNew++));
        while (curOld < hunk.start_old) out.push(ctx(curOld++, curNew));
        while (curNew < hunk.start_new) out.push(ctx(curOld, curNew++));
        out.push(...hunkRows(hunk));
        for (const line of hunk.lines) {
          if (line.line_old !== null) curOld = line.line_old + 1;
          if (line.line_new !== null) curNew = line.line_new + 1;
        }
      }
      while (curOld <= linesOld.length && curNew <= linesNew.length) out.push(ctx(curOld++, curNew++));
      return out;
    }
    return hunks.flatMap((h): Row[] => [{ t: 'hunk', header: h.header }, ...hunkRows(h)]);
  });
</script>

{#snippet segs(row: { text: string; segments: DiffSegment[] | null }, show: 'del' | 'ins')}
  {#if row.segments}
    {#each row.segments as s, i (i)}
      {#if s.type === 'eq'}{s.text}{:else if s.type === show}<span class="diff-word-{show === 'del' ? 'del' : 'add'}">{s.text}</span
        >{/if}
    {/each}
  {:else}
    {row.text}
  {/if}
{/snippet}

{#if !rows.length}
  <div class="diff-empty-msg">Files are identical — no changes.</div>
{:else if mode === 'split'}
  <table class="diff-table diff-table--split">
    <colgroup><col style="width:44px" /><col /><col style="width:44px" /><col /></colgroup>
    <tbody>
      {#each rows as r, i (i)}
        {#if r.t === 'hunk'}
          <tr class="diff-hunk-hdr"><td colspan="4" class="diff-hunk-hdr-cell">{r.header}</td></tr>
        {:else if r.t === 'ctx'}
          <tr class="diff-ctx">
            <td class="diff-ln">{r.lo}</td><td class="diff-code">{r.oldText}</td>
            <td class="diff-ln">{r.ln}</td><td class="diff-code">{r.text}</td>
          </tr>
        {:else if r.t === 'del'}
          <tr>
            <td class="diff-ln diff-del">{r.lo ?? ''}</td><td class="diff-code diff-del">{@render segs(r, 'del')}</td>
            <td class="diff-ln diff-empty-side"></td><td class="diff-code diff-empty-side"></td>
          </tr>
        {:else}
          <tr>
            <td class="diff-ln diff-empty-side"></td><td class="diff-code diff-empty-side"></td>
            <td class="diff-ln diff-add">{r.ln ?? ''}</td><td class="diff-code diff-add">{@render segs(r, 'ins')}</td>
          </tr>
        {/if}
      {/each}
    </tbody>
  </table>
{:else}
  <table class="diff-table diff-table--inline">
    <tbody>
      {#each rows as r, i (i)}
        {#if r.t === 'hunk'}
          <tr class="diff-hunk-hdr"><td colspan="4" class="diff-hunk-hdr-cell">{r.header}</td></tr>
        {:else if r.t === 'ctx'}
          <tr class="diff-ctx">
            <td class="diff-ln">{r.lo}</td><td class="diff-ln">{r.ln}</td><td class="diff-sign"> </td><td class="diff-code">{r.text}</td>
          </tr>
        {:else if r.t === 'del'}
          <tr class="diff-del">
            <td class="diff-ln">{r.lo ?? ''}</td><td class="diff-ln"></td><td class="diff-sign">−</td>
            <td class="diff-code">{@render segs(r, 'del')}</td>
          </tr>
        {:else}
          <tr class="diff-add">
            <td class="diff-ln"></td><td class="diff-ln">{r.ln ?? ''}</td><td class="diff-sign">+</td>
            <td class="diff-code">{@render segs(r, 'ins')}</td>
          </tr>
        {/if}
      {/each}
    </tbody>
  </table>
{/if}
