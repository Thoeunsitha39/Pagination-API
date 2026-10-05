"""{{...}} response templating (WireMock response-template style)."""

import json
import random
import re
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from api_tool.core.scripting.script_request import MultiStr, PathStr


_TEMPLATE_RE = re.compile(r"\{\{\s*(.*?)\s*\}\}", re.DOTALL)


_TOKEN_RE = re.compile(
    r"""\s*(?:
        (?P<kw>\w+)=(?:'(?P<kwsq>[^']*)'|"(?P<kwdq>[^"]*)"|(?P<kwbare>\S+))
      | '(?P<sq>[^']*)'
      | "(?P<dq>[^"]*)"
      | (?P<bare>[^\s'"]+)
    )""",
    re.VERBOSE,
)


_PATH_PART_RE = re.compile(r"\[(\d+)\]|([^.\[\]]+)")


def _tokenize(expression):
    args, kwargs = [], {}
    for match in _TOKEN_RE.finditer(expression):
        if match.group("kw"):
            value = next(
                v for v in (match.group("kwsq"), match.group("kwdq"), match.group("kwbare")) if v is not None
            )
            kwargs[match.group("kw")] = value
        elif match.group("sq") is not None:
            args.append(("lit", match.group("sq")))
        elif match.group("dq") is not None:
            args.append(("lit", match.group("dq")))
        elif match.group("bare"):
            bare = match.group("bare")
            if re.fullmatch(r"-?\d+(\.\d+)?", bare):
                args.append(("lit", bare))
            else:
                args.append(("ref", bare))
    return args, kwargs


def resolve(path, context):
    """Look up a dotted path like request.query.user or vars.items.[0].name; None if missing."""
    current = context
    for index, name in _PATH_PART_RE.findall(path):
        if current is None:
            return None
        if index:
            position = int(index)
            if isinstance(current, PathStr):
                current = current.segments
            elif isinstance(current, MultiStr):
                current = current.values
            current = current[position] if isinstance(current, list) and position < len(current) else None
        elif isinstance(current, dict):
            current = current.get(name)
        else:
            current = getattr(current, name, None)
    return current


def _to_text(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def json_path(source, path):
    """Minimal JSONPath: $.a.b, $.a[0], $['a b'], $.a[-1]."""
    data = source
    if isinstance(source, str):
        try:
            data = json.loads(source)
        except ValueError:
            return None
    path = path.strip()
    if path.startswith("$"):
        path = path[1:]
    for key, index, quoted_sq, quoted_dq in re.findall(
        r"\.([^.\[\]]+)|\[(-?\d+)\]|\['([^']*)'\]|\[\"([^\"]*)\"\]", path
    ):
        if index:
            position = int(index)
            if not isinstance(data, list) or not -len(data) <= position < len(data):
                return None
            data = data[position]
        else:
            name = key or quoted_sq or quoted_dq
            if not isinstance(data, dict) or name not in data:
                return None
            data = data[name]
    return data


def x_path(source, path):
    """Minimal XPath: /root/child, //child, /root/child/@attr, /root/items/item[2] (1-based)."""
    try:
        root = source if isinstance(source, ET.Element) else ET.fromstring(source)
    except (ET.ParseError, TypeError):
        return None
    path = path.strip()
    attribute = None
    if "/@" in path:
        path, attribute = path.rsplit("/@", 1)
    wrapper = ET.Element("_document")
    wrapper.append(root)
    if path.startswith("//"):
        query = ".//" + path[2:]
    elif path.startswith("/"):
        query = "./" + path[1:]
    else:
        query = ".//" + path
    try:
        element = wrapper.find(query) if query not in ("./", ".//") else root
    except SyntaxError:
        return None
    if element is None:
        return None
    if attribute is not None:
        return element.get(attribute)
    return (element.text or "").strip()


def _helper(name, values, kwargs):
    if name == "now":
        moment = datetime.now(timezone.utc)
        fmt = values[0] if values else kwargs.get("format")
        return moment.strftime(fmt) if fmt else moment.strftime("%Y-%m-%dT%H:%M:%SZ")
    if name == "uuid":
        return str(uuid.uuid4())
    if name == "randomInt":
        low = int(values[0]) if values else 0
        high = int(values[1]) if len(values) > 1 else 100
        return random.randint(low, high)
    if name == "jsonPath":
        return json_path(values[0], values[1]) if len(values) > 1 else None
    if name == "xPath":
        return x_path(values[0], values[1]) if len(values) > 1 else None
    if name == "upper":
        return _to_text(values[0]).upper() if values else ""
    if name == "lower":
        return _to_text(values[0]).lower() if values else ""
    raise KeyError(name)


HELPERS = {"now", "uuid", "randomInt", "jsonPath", "xPath", "upper", "lower"}


def _evaluate(expression, context):
    args, kwargs = _tokenize(expression)
    if not args:
        return None
    kind, first = args[0]
    if kind == "ref" and first in HELPERS:
        values = [value if k == "lit" else resolve(value, context) for k, value in args[1:]]
        result = _helper(first, values, kwargs)
    elif kind == "ref":
        result = resolve(first, context)
    else:
        result = first
    if (result is None or result == "") and "default" in kwargs:
        result = kwargs["default"]
    return result


def render_template(text, context):
    """Replace every {{...}} in text. Unknown values render as empty text."""
    if not text or "{{" not in text:
        return text
    return _TEMPLATE_RE.sub(lambda m: _to_text(_evaluate(m.group(1), context)), text)


_SINGLE_PLACEHOLDER_RE = re.compile(r"\{\{\s*([^{}]*?)\s*\}\}")


def render_json_template(value, context):
    """Fill a parsed JSON template. A string that is exactly one placeholder ("{{page.items}}")
    becomes the value itself (array, number, true/false, null); other strings are rendered as text."""
    if isinstance(value, str):
        single = _SINGLE_PLACEHOLDER_RE.fullmatch(value.strip())
        if single:
            return _evaluate(single.group(1), context)
        return render_template(value, context)
    if isinstance(value, list):
        return [render_json_template(entry, context) for entry in value]
    if isinstance(value, dict):
        return {key: render_json_template(entry, context) for key, entry in value.items()}
    return value


def render_values(value, context):
    """Fill {{...}} in every string inside parsed JSON (dicts, lists), keeping the structure valid."""
    if isinstance(value, str):
        return render_template(value, context)
    if isinstance(value, list):
        return [render_values(entry, context) for entry in value]
    if isinstance(value, dict):
        return {key: render_values(entry, context) for key, entry in value.items()}
    return value


def template_context(request, variables=None, response=None):
    context = {"request": request, "originalRequest": request, "vars": variables or {}}
    if response is not None:
        context["response"] = response
    return context
