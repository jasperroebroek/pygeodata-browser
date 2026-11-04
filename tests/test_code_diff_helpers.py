"""Structured diff helpers (_word_segments, _build_structured_hunks) from code_service."""

from pygeodata_browser.code_service import _build_structured_hunks, _word_segments

# ===========================================================================
# Structured diff: _word_segments
# ===========================================================================


def test_word_segments():
    # identical lines → all eq
    segs_old, segs_new = _word_segments('hello world', 'hello world')
    assert all(s.type == 'eq' for s in segs_old)
    assert all(s.type == 'eq' for s in segs_new)
    assert ''.join(s.text for s in segs_old) == 'hello world'

    # single word change → del in old, ins in new, text reconstructed
    segs_old, segs_new = _word_segments('x = 1', 'x = 2')
    assert ''.join(s.text for s in segs_old) == 'x = 1'
    assert ''.join(s.text for s in segs_new) == 'x = 2'
    assert any(s.type == 'del' and '1' in s.text for s in segs_old)
    assert any(s.type == 'ins' and '2' in s.text for s in segs_new)

    # new side never contains del; old side never contains ins
    segs_old, segs_new = _word_segments('old value', 'new value')
    assert all(s.type != 'del' for s in segs_new)
    assert all(s.type != 'ins' for s in segs_old)


# ===========================================================================
# Structured diff: _build_structured_hunks
# ===========================================================================


def test_structured_hunks_shape():
    # identical files → empty
    assert _build_structured_hunks('class A: pass\n', 'class A: pass\n') == []

    # single-line change: hunk keys, line types, line numbers
    hunks = _build_structured_hunks('x = 1\n', 'x = 2\n')
    assert len(hunks) == 1
    hunk = hunks[0]
    assert hunk.header.startswith('@@')
    assert hunk.start_old == 1
    assert hunk.start_new == 1

    all_lines = [ln for h in hunks for ln in h.lines]
    types = {ln.type for ln in all_lines}
    assert 'del' in types and 'add' in types

    # line number fields per type
    hunks2 = _build_structured_hunks('x = 1\ny = 2\n', 'x = 1\ny = 3\n')
    all2 = [ln for h in hunks2 for ln in h.lines]
    ctx = [ln for ln in all2 if ln.type == 'ctx']
    dels = [ln for ln in all2 if ln.type == 'del']
    adds = [ln for ln in all2 if ln.type == 'add']
    assert all(ln.line_old is not None and ln.line_new is not None for ln in ctx)
    assert all(ln.line_old is not None and ln.line_new is None for ln in dels)
    assert all(ln.line_old is None and ln.line_new is not None for ln in adds)

    # ctx lines have no segments; changed lines do
    old3 = 'a\nb\nc\n'
    new3 = 'a\nB\nc\n'
    hunks3 = _build_structured_hunks(old3, new3)
    all3 = [ln for h in hunks3 for ln in h.lines]
    assert all(ln.segments is None for ln in all3 if ln.type == 'ctx')


def test_structured_hunks_content():
    # paired del/add lines get segments
    hunks = _build_structured_hunks('x = 1\n', 'x = 2\n')
    all_lines = [ln for h in hunks for ln in h.lines]
    del_line = next(ln for ln in all_lines if ln.type == 'del')
    add_line = next(ln for ln in all_lines if ln.type == 'add')
    assert del_line.segments is not None
    assert add_line.segments is not None

    # text reconstruction
    old = 'line1\nline2\nline3\n'
    new = 'line1\nLINE2\nline3\n'
    hunks2 = _build_structured_hunks(old, new)
    all2 = [ln for h in hunks2 for ln in h.lines]
    assert [ln.text for ln in all2 if ln.type == 'del'] == ['line2']
    assert [ln.text for ln in all2 if ln.type == 'add'] == ['LINE2']
