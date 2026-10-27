import json
from pathlib import Path

import pytest

from pygeodata_browser.popups import (
    _inject_graph_links,
    build_json_popup,
)

# --- _inject_graph_links ---


def test_inject_graph_links_adds_data_cls() -> None:
    svg = '<g id="node1" class="node">\n<title>MyLoader</title><text>x</text></g>'
    result = _inject_graph_links(svg, frozenset({'MyLoader'}))
    assert 'data-cls="MyLoader"' in result
    assert 'graph-node-link' in result


def test_inject_graph_links_unknown_class_unchanged() -> None:
    svg = '<g id="node1" class="node">\n<title>UnknownLoader</title><text>x</text></g>'
    result = _inject_graph_links(svg, frozenset({'KnownLoader'}))
    assert 'data-cls' not in result


def test_inject_graph_links_empty_svg() -> None:
    assert _inject_graph_links('', frozenset({'MyLoader'})) == ''


# --- build_json_popup ---


def test_build_json_popup_valid(tmp_path: Path) -> None:
    f = tmp_path / 'data.json'
    f.write_text(json.dumps({'key': 'value'}))
    result = build_json_popup(str(f))
    assert result['title'] == 'data.json'
    assert result['json'] == {'key': 'value'}


def test_build_json_popup_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        build_json_popup(str(tmp_path / 'nope.json'))


def test_build_json_popup_invalid_json(tmp_path: Path) -> None:
    f = tmp_path / 'bad.json'
    f.write_text('not json')
    with pytest.raises(ValueError, match='Invalid JSON'):
        build_json_popup(str(f))
