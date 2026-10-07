import pytest

from api_tool.core.beautify import beautify, sniff_format


def test_json_with_block_helpers_between_values_is_refused():
    with pytest.raises(ValueError, match="not valid JSON"):
        beautify('{"tags":[{{#each x}}1{{/each}}]}', "json")


def test_json_simple_templates():
    assert beautify('{"a":{{n}},"b":"x {{y}} z"}', "json") == '{\n  "a": {{n}},\n  "b": "x {{y}} z"\n}'


def test_xml_and_errors():
    assert beautify("<a><b>{{x}}</b></a>", "xml") == "<a>\n  <b>{{x}}</b>\n</a>"
    with pytest.raises(ValueError, match="not valid JSON"):
        beautify('{"a": ', "json")
    with pytest.raises(ValueError):
        beautify("plain text", None)


def test_sniff_format():
    assert sniff_format("<x/>", "application/json") == "json"
    assert sniff_format("  [1]") == "json"
    assert sniff_format("<x/>") == "xml"
    assert sniff_format("hello") is None
