"""Pretty-print JSON and XML bodies, leaving {{template}} placeholders as they were written."""

import json
import re
import xml.etree.ElementTree as ET

_TEMPLATE = re.compile(r"\{\{.*?\}\}", re.DOTALL)


def sniff_format(text, content_type=""):
    """'json', 'xml' or None, from the Content-Type if it says, else from the body's first character."""
    content_type = (content_type or "").lower()
    if "json" in content_type:
        return "json"
    if "xml" in content_type:
        return "xml"
    start = text.lstrip()[:1]
    return "json" if start in ("{", "[") else "xml" if start == "<" else None


def _hide_templates_in_json(text):
    """Swap each {{...}} for a placeholder that keeps the JSON valid, and return how to swap back.

    A template inside a string becomes plain text; one standing in for a value (e.g. "id": {{n}})
    becomes a quoted string, unquoted again after formatting."""
    out, originals = [], []
    in_string = escaped = False
    i = 0
    while i < len(text):
        match = _TEMPLATE.match(text, i) if text.startswith("{{", i) else None
        if match:
            token = f"__tpl_{'s' if in_string else 'v'}{len(originals)}__"
            originals.append((token if in_string else f'"{token}"', match.group()))
            out.append(originals[-1][0])
            i = match.end()
            continue
        char = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        out.append(char)
        i += 1

    def restore(pretty):
        for placeholder, original in originals:
            pretty = pretty.replace(placeholder, original, 1)
        return pretty

    return "".join(out), restore


def beautify(text, fmt):
    """The body pretty-printed as fmt ('json' or 'xml'). Raises ValueError if it can't be parsed."""
    if fmt == "json":
        hidden, restore = _hide_templates_in_json(text)
        try:
            data = json.loads(hidden)
        except ValueError as exc:
            raise ValueError(f"Body is not valid JSON: {exc}") from exc
        return restore(json.dumps(data, indent=2, ensure_ascii=False))
    if fmt == "xml":
        try:
            root = ET.fromstring(text)
        except ET.ParseError as exc:
            raise ValueError(f"Body is not valid XML: {exc}") from exc
        ET.indent(root)
        pretty = ET.tostring(root, encoding="unicode")
        if text.lstrip().startswith("<?xml"):
            pretty = '<?xml version="1.0" encoding="UTF-8"?>\n' + pretty
        return pretty
    raise ValueError("Beautify works on JSON and XML bodies")
