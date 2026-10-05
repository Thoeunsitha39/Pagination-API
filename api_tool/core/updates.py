"""Checks GitHub Releases for a newer version of API Tool.

A release is published by pushing a tag such as `v2.1` (see .github/workflows/release.yml);
the app compares the latest release's tag with api_tool.__version__."""

import json
import os
import re
import urllib.error
import urllib.request

from api_tool import __version__

GITHUB_REPO = "Thoeunsitha39/Pagination-API"
LATEST_RELEASE_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
RELEASES_PAGE_URL = f"https://github.com/{GITHUB_REPO}/releases/latest"


def parse_version(text):
    """'v2.1.3' -> (2, 1, 3). Trailing zeros are dropped so '2.0' == '2'."""
    parts = [int(n) for n in re.findall(r"\d+", text.split("-")[0])]
    while parts and parts[-1] == 0:
        parts.pop()
    return tuple(parts)


def is_newer(latest, current=__version__):
    return parse_version(latest) > parse_version(current)


def updates_disabled():
    """Set API_TOOL_NO_UPDATE_CHECK=1 to never contact GitHub (also used by the tests)."""
    return bool(os.environ.get("API_TOOL_NO_UPDATE_CHECK"))


def fetch_latest_release(timeout=8):
    """Return {'version', 'url', 'notes'} for the latest release.

    Raises OSError / ValueError when GitHub can't be reached or answers oddly."""
    request = urllib.request.Request(
        LATEST_RELEASE_URL,
        headers={"Accept": "application/vnd.github+json", "User-Agent": f"APITool/{__version__}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise ValueError("No release has been published on GitHub yet") from exc
        raise
    tag = data.get("tag_name")
    if not tag:
        raise ValueError("The latest release has no tag")
    return {
        "version": tag.lstrip("vV"),
        "url": data.get("html_url") or RELEASES_PAGE_URL,
        "notes": (data.get("body") or "").strip(),
    }


def main():
    """`python -m api_tool.core.updates`: show the upgrade message installed apps get right now."""
    try:
        release = fetch_latest_release()
    except Exception as exc:
        print(f"FAIL  {exc}")
        return 1
    print(f"Latest release on GitHub: {release['version']}  ({release['url']})")
    print(f"This code's version:      {__version__}")
    for old in dict.fromkeys(("2.0", "2.1", "2.2", "2.2.1", __version__)):
        shown = "sees the upgrade message" if is_newer(release["version"], old) else "up to date"
        print(f"  an app on {old:<6} {shown}")
    print("\nMessage text:")
    print(f"  API Tool {release['version']} is available")
    print("  You have <their version>.")
    for line in release["notes"].splitlines() or ["(no release notes)"]:
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
