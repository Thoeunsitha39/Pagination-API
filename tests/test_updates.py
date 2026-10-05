"""Version comparison for the "update available" notice."""

from api_tool.core.updates import is_newer, parse_version


def test_parse_version_ignores_prefix_and_trailing_zeros():
    assert parse_version("v2.1.3") == (2, 1, 3)
    assert parse_version("2.0") == parse_version("2") == parse_version("v2.0.0")


def test_is_newer():
    assert is_newer("v2.1", "2.0")
    assert is_newer("2.10", "2.9")  # numeric, not alphabetical
    assert is_newer("3", "2.9.9")
    assert not is_newer("v2.0", "2.0")
    assert not is_newer("1.9", "2.0")
    assert not is_newer("2.1-beta", "2.1")
