import json
from pathlib import Path

import pytest
from conftest import make_analysis
from pygeodata_browser.contracts import JsonPopup
from pygeodata_browser.popups import (
    _dependency_graph,
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


# --- _dependency_graph ---


def test_dependency_graph_comes_from_the_analysis() -> None:
    analysis = make_analysis(Child='c', Parent='p')
    child = analysis.classes['Child']
    analysis.classes['Child'] = type(child)(
        facts=type(child.facts)(
            name='Child',
            object_type='Table',
            source_hash='c',
            call_deps=frozenset({'Parent'}),
            bases=frozenset(),
        ),
        path=child.path,
        lineno=child.lineno,
        tree_hash=child.tree_hash,
    )

    graph = _dependency_graph(analysis, 'Child')

    assert {node.name for node in graph.nodes} == {'Child', 'Parent'}
    assert {(s.name, t.name) for s, t in graph.call_edges} == {('Child', 'Parent')}
    assert {node.name: node.color for node in graph.nodes} == {'Child': '#c9d8c5', 'Parent': '#d0dceb'}


# --- build_json_popup ---


def test_build_json_popup_valid(tmp_path: Path) -> None:
    f = tmp_path / 'data.json'
    f.write_text(json.dumps({'key': 'value'}))
    result = build_json_popup(str(f))
    assert result == JsonPopup(title='data.json', json={'key': 'value'})


def test_build_json_popup_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        build_json_popup(str(tmp_path / 'nope.json'))


def test_build_json_popup_invalid_json(tmp_path: Path) -> None:
    f = tmp_path / 'bad.json'
    f.write_text('not json')
    with pytest.raises(ValueError, match='Invalid JSON'):
        build_json_popup(str(f))
