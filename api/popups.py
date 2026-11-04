import html
import json
import logging
import re
import tempfile
from pathlib import Path

from pygeodata.analysis import ProjectAnalysis
from pygeodata.data import Data
from pygeodata.dependencies import dependency_tree
from pygeodata.figure import Figure
from pygeodata.graph_types import ClassNode, DependencyGraph
from pygeodata.graphs import plot_class_dependency_graph
from pygeodata.table import Table
from pygeodata.tracked_object import TrackedObject

logger = logging.getLogger(__name__)

_COLORS = {cls.get_class_name(): cls.color for cls in (TrackedObject, Data, Table, Figure)}


def _dependency_graph(analysis: ProjectAnalysis, class_name: str) -> DependencyGraph:
    facts = analysis.facts
    tree = dependency_tree(facts.__getitem__, class_name)

    def node(name: str) -> ClassNode:
        return ClassNode(cls=object, name=name, color=_COLORS.get(facts[name].object_type, TrackedObject.color))

    return DependencyGraph(
        nodes={node(name) for name in tree.nodes},
        call_edges={(node(s), node(t)) for s, t in tree.call_edges},
        inheritance_edges={(node(s), node(t)) for s, t in tree.inheritance_edges},
    )


def build_json_popup(file_path: str) -> dict:
    """Return JSON file contents as parsed data for the client-side explorer."""
    path = Path(file_path)
    try:
        data = json.loads(path.read_text())
    except OSError as exc:
        raise FileNotFoundError(file_path) from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f'Invalid JSON: {file_path}') from exc

    return {
        'title': path.name,
        'json': data,
    }


def _inject_graph_links(svg: str, known_classes: frozenset[str]) -> str:
    """Add data-cls attributes to graphviz node <g> elements so JS can make them clickable."""

    # Each node group looks like: <g id="nodeN" class="node">\n<title>ClassName</title>
    def replace_node(m: re.Match) -> str:
        g_attrs = m.group(1)
        title = m.group(2)
        rest = m.group(3)
        if title in known_classes:
            merged_attrs = g_attrs.replace('class="node"', 'class="node graph-node-link"')
            return f'<g {merged_attrs} data-cls="{html.escape(title)}">\n<title>{html.escape(title)}</title>{rest}'
        return m.group(0)

    pattern = re.compile(
        r'<g ([^>]*class="node"[^>]*)>\s*<title>([^<]+)</title>(.*?)</g>',
        re.DOTALL,
    )
    return pattern.sub(replace_node, svg)


def build_graph_popup(class_name: str, analysis: ProjectAnalysis, graph_path: str | None = None) -> dict[str, str]:
    logger.info('Building graph popup for class %s', class_name)

    if class_name in analysis.classes:
        graph_data = _dependency_graph(analysis, class_name)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / f'{class_name}.svg'
            plot_class_dependency_graph(class_name, graph_data, path=path, view=False)
            svg = path.read_text(encoding='utf-8') if path.exists() else None

        if svg is None:
            logger.error('Dependency graph SVG was not created for class %s', class_name)
            raise FileNotFoundError(class_name)

        known_classes = frozenset(analysis.classes)
        svg = _inject_graph_links(svg, known_classes)

        return {
            'title': f'Graph · {class_name}',
            'svg': svg,
        }

    # Class not in the project — serve the pre-rendered PDF path for the frontend to display
    if graph_path is not None:
        return {
            'title': f'Graph · {class_name}',
            'pdf_path': graph_path,
        }

    logger.error('Cannot build graph popup: class not in the project and no graph_path: %s', class_name)
    raise KeyError(class_name)
