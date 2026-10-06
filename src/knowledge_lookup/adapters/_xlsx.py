"""Minimal read-only ``.xlsx`` reader built on the standard library.

``openpyxl`` is not a core dependency, and the datasets that need this reader (CellMarker's
``Cell_marker_*.xlsx``, about a million rows) are plain single-sheet tables, so a small
streaming parser is enough: ``zipfile`` + ``xml.etree.ElementTree.iterparse``.

Scope and limits:

* only the **first sheet** (as ordered in ``xl/workbook.xml``) is read;
* values are returned as strings: shared strings (including rich text runs), inline strings
  and raw ``<v>`` values; formulas are not evaluated, number formats and dates are not
  interpreted (a date cell yields its serial number);
* empty cells become ``""`` so row lists stay aligned with column positions;
* rows are streamed, never materialised, and each parsed XML element is released at once.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Iterator
from pathlib import Path

_MAIN_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_PKG_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_COL_RE = re.compile(r"([A-Za-z]+)")


def _column_index(ref: str) -> int:
    """``"A1"`` -> 0, ``"B7"`` -> 1, ``"AA3"`` -> 26."""
    match = _COL_RE.match(ref)
    if not match:
        return 0
    index = 0
    for char in match.group(1).upper():
        index = index * 26 + (ord(char) - 64)
    return index - 1


def _first_sheet_member(archive: zipfile.ZipFile) -> str:
    """Archive member holding the first worksheet (falls back to ``sheet1.xml``)."""
    names = set(archive.namelist())
    try:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        sheet = workbook.find(f"{_MAIN_NS}sheets/{_MAIN_NS}sheet")
        rel_id = sheet.get(f"{_REL_NS}id") if sheet is not None else None
        if rel_id:
            rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
            for rel in rels.findall(f"{_PKG_REL_NS}Relationship"):
                if rel.get("Id") == rel_id:
                    target = (rel.get("Target") or "").lstrip("/")
                    member = target if target.startswith("xl/") else f"xl/{target}"
                    if member in names:
                        return member
    except (KeyError, ET.ParseError):
        pass
    if "xl/worksheets/sheet1.xml" in names:
        return "xl/worksheets/sheet1.xml"
    sheets = sorted(n for n in names if n.startswith("xl/worksheets/") and n.endswith(".xml"))
    if not sheets:
        raise ValueError("no worksheet found in xlsx file")
    return sheets[0]


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    """All entries of ``xl/sharedStrings.xml`` (rich-text runs are concatenated)."""
    try:
        member = archive.open("xl/sharedStrings.xml")
    except KeyError:
        return []
    strings: list[str] = []
    with member:
        for _event, elem in ET.iterparse(member, events=("end",)):
            if elem.tag == f"{_MAIN_NS}si":
                strings.append("".join(t.text or "" for t in elem.iter(f"{_MAIN_NS}t")))
                elem.clear()
    return strings


def iter_xlsx_rows(path: str | Path) -> Iterator[list[str]]:
    """Yield the rows of the first sheet of ``path`` as lists of strings."""
    with zipfile.ZipFile(path) as archive:
        shared = _shared_strings(archive)
        member = _first_sheet_member(archive)
        row_tag, cell_tag = f"{_MAIN_NS}row", f"{_MAIN_NS}c"
        value_tag, inline_tag = f"{_MAIN_NS}v", f"{_MAIN_NS}is"
        with archive.open(member) as handle:
            for _event, row in ET.iterparse(handle, events=("end",)):
                if row.tag != row_tag:
                    continue
                values: list[str] = []
                for cell in row.iter(cell_tag):
                    position = _column_index(cell.get("r", ""))
                    if position < len(values):
                        position = len(values)  # malformed/missing ref: append in order
                    values.extend([""] * (position - len(values)))
                    kind = cell.get("t")
                    if kind == "inlineStr":
                        inline = cell.find(inline_tag)
                        text = (
                            "".join(t.text or "" for t in inline.iter(f"{_MAIN_NS}t"))
                            if inline is not None
                            else ""
                        )
                    else:
                        node = cell.find(value_tag)
                        text = (node.text or "") if node is not None else ""
                        if kind == "s" and text:
                            try:
                                text = shared[int(text)]
                            except (ValueError, IndexError):
                                text = ""
                    values.append(text)
                row.clear()
                yield values
