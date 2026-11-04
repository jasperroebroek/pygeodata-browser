"""The Python contracts and the TypeScript interfaces that mirror them name the same fields."""

import dataclasses
import re
from pathlib import Path

import msgspec
from pygeodata_browser import contracts
import pytest
from pygeodata.views.types import CodeClassState
from pygeodata_browser.contracts import (
    DetailRow,
    HeaderRow,
    LoadingPayload,
    ParamRowPayload,
)

LIB = Path(__file__).parent.parent / 'app' / 'src' / 'lib'

# TypeScript name -> the contract classes whose fields it spells out (several: a union or an optional-keyed superset)
MIRRORS: dict[str, tuple[type, ...]] = {
    'SpecPayload': (contracts.SpecInfo,),
    'ClassCard': (contracts.ClassCard,),
    'TableRow': (contracts.HeaderRow, contracts.DetailRow),
    'FilePayload': (contracts.FileRef,),
    'ParamRow': (contracts.ParamRowPayload,),
    'FoundEntry': (contracts.EntryRef,),
    'FoundEntries': (contracts.FoundEntries,),
    'PinsPayload': (contracts.PinsPayload,),
    'CleanResult': (contracts.CleanResult,),
    'JsonPopup': (contracts.JsonPopup,),
    'GraphPopup': (contracts.GraphSvgPopup, contracts.GraphPdfPopup),
    'LinkedEntry': (contracts.LinkedEntryPayload,),
    'CoOutput': (contracts.CoOutput,),
    'SameInstanceRun': (contracts.SameInstanceRun,),
    'DepVersionSibling': (contracts.DepVersionSibling,),
    'EntryDetail': (contracts.EntryDetail,),
    'CodeVersionEntry': (contracts.CodeVersionEntry,),
    'DetailPayload': (contracts.DetailPayload,),
    'VersionOption': (contracts.VersionOption,),
    'StatusPayload': (contracts.StatusPayload,),
    'UnavailableRoot': (contracts.UnavailableRoot,),
    'CatalogInfo': (contracts.CatalogInfo,),
    'Diagnostics': (contracts.Diagnostics,),
    'SpecOption': (contracts.SpecOption,),
    'SpecOptions': (contracts.SpecOptions,),
    'Counts': (contracts.Counts,),
    'ClassesPayload': (contracts.ClassesPayload,),
    'EntriesPagePayload': (contracts.EntriesPage,),
    'BootstrapRow': (contracts.BootstrapRow,),
    'CodeClassState': (CodeClassState,),
    'SnapshotLine': (contracts.SnapshotLine,),
    'SnapshotPayload': (contracts.SnapshotPayload,),
    'DiffSegment': (contracts.DiffSegment,),
    'DiffLine': (contracts.DiffLine,),
    'DiffHunk': (contracts.DiffHunk,),
    'DiffPayload': (contracts.FullDiffPayload,),
    'VersionChange': (contracts.VersionChange,),
    'VersionDiffPayload': (contracts.VersionDiff, contracts.VersionDiffError),
    'ResolvedDepHash': (contracts.ResolvedDepHash,),
    'ResolvedSourceHash': (contracts.ResolvedSourceHash,),
    'VersionsPayload': (contracts.VersionsPayload,),
    'LoadingPayload': (contracts.LoadingPayload,),
    'ExportStartResult': (contracts.ExportStart,),
    'ExportStatusResult': (contracts.ExportStatus,),
    'ExportTableResult': (contracts.ExportTable,),
}

# contracts the frontend does not read, or only as a base of one it does
UNMIRRORED = {'Ok', 'EntryIds', 'ClassDetail', 'DiffPayload'}

_DECLARATION = re.compile(r'^export (?:interface (\w+)|type (\w+) =) \{\n(.*?)^\}', re.MULTILINE | re.DOTALL)
_FIELD = re.compile(r'^  (\w+)\??:', re.MULTILINE)


def ts_fields() -> dict[str, set[str]]:
    declared: dict[str, set[str]] = {}
    for path in LIB.glob('api*.ts'):
        for match in _DECLARATION.finditer(path.read_text()):
            declared[match[1] or match[2]] = set(_FIELD.findall(match[3]))
    return declared


def names(classes: tuple[type, ...]) -> set[str]:
    return {f.name for cls in classes for f in dataclasses.fields(cls)}


@pytest.mark.skipif(not LIB.is_dir(), reason='frontend sources not present')
def test_typescript_interfaces_name_the_contract_fields() -> None:
    declared = ts_fields()
    assert set(MIRRORS) <= set(declared), 'interface missing in the frontend'
    assert {name: fields for name, fields in declared.items() if name in MIRRORS} == {
        name: names(classes) for name, classes in MIRRORS.items()
    }


def test_every_contract_is_mirrored_or_exempt() -> None:
    defined = {
        name
        for name, obj in vars(contracts).items()
        if isinstance(obj, type) and dataclasses.is_dataclass(obj) and obj.__module__ == contracts.__name__
    }
    mirrored = {cls.__name__ for classes in MIRRORS.values() for cls in classes}
    assert defined - mirrored == UNMIRRORED


def test_detail_rows_flatten_the_parameter_row() -> None:
    row = ParamRowPayload(
        group='g',
        parameter='p',
        value='v',
        value_type='int',
        param_row_type='value',
        path='g.p',
        depth=1,
    )
    encoded = msgspec.json.decode(msgspec.json.encode(DetailRow(**vars(row), class_name='C', record_id='r')))
    assert encoded == {**vars(row), 'class_name': 'C', 'record_id': 'r', 'row_type': 'detail'}


def test_header_rows_carry_their_row_type() -> None:
    assert HeaderRow.__dataclass_fields__['row_type'].default == 'header'


def test_loading_payload_keys() -> None:
    assert msgspec.json.decode(msgspec.json.encode(LoadingPayload(fast=True))) == {'fast': True, 'loading': True}
