"""Parsing JSON / XML / CSV payload files into record lists."""

import csv
import io
import json
import re
import xml.etree.ElementTree as ET


_NUMBER_RE = re.compile(r"-?(0|[1-9]\d*)(\.\d+)?([eE][-+]?\d+)?")


def _coerce(text):
    """Turn numeric-looking text into int/float. Leading zeros (IDs, zip codes),
    "nan", and "inf" stay strings, so records always round-trip as valid JSON."""
    if text is None:
        return None
    text = text.strip()
    if not _NUMBER_RE.fullmatch(text):
        return text
    if text.lstrip("-").isdigit():
        return int(text)
    return float(text)


def parse_json_items(text):
    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError("JSON payload must be a top-level list of items")
    return data


def _element_to_obj(el):
    children = list(el)
    if not children:
        return _coerce(el.text)
    obj = {}
    for child in children:
        value = _element_to_obj(child)
        if child.tag in obj:
            existing = obj[child.tag]
            if isinstance(existing, list):
                existing.append(value)
            else:
                obj[child.tag] = [existing, value]
        else:
            obj[child.tag] = value
    return obj


def parse_xml_items(text):
    root = ET.fromstring(text)
    return [_element_to_obj(el) for el in root]


def parse_csv_items(text, has_header):
    rows = [row for row in csv.reader(io.StringIO(text)) if row]
    if not rows:
        return []

    if has_header:
        header = [name.strip() for name in rows[0]]
        data_rows = rows[1:]
    else:
        header = [f"column_{i + 1}" for i in range(max(len(row) for row in rows))]
        data_rows = rows

    items = []
    for row in data_rows:
        obj = {}
        for i, key in enumerate(header):
            key = key or f"column_{i + 1}"
            value = row[i] if i < len(row) else None
            obj[key] = _coerce(value)
        items.append(obj)
    return items
