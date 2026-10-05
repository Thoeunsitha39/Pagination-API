"""Free-AI offers: a notification with a Claim button that sets up the AI assistant in one click.

The offer in notifications.json points at a config file (kept out of the repo, e.g. a secret gist):

    {"provider": "deepseek", "base_url": "https://api.deepseek.com/anthropic",
     "model": "deepseek-v4-pro", "api_key": "sk-…", "expires_at": "2026-10-12T23:59:59+07:00"}

Anyone who can download the config can copy the key, and the end date is only enforced by this app.
Use a key made for the offer, with a small balance / spend limit, and delete it when the offer ends."""

import json
import urllib.request
from datetime import datetime, timezone

from api_tool import __version__
from api_tool.ai.settings import PROVIDERS, AISettings


def fetch_offer_config(url, timeout=8):
    """The config dict from url. Raises OSError / ValueError on failure."""
    request = urllib.request.Request(url, headers={"User-Agent": f"APITool/{__version__}"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("The offer config is not a JSON object")
    return data


def settings_from_offer(config, offer_id, share_context=True, now=None):
    """AISettings for a claimed offer. Raises ValueError when the config is incomplete or ended."""
    provider = config.get("provider") or "anthropic_compat"
    if provider not in PROVIDERS:
        raise ValueError(f"Unknown AI provider \"{provider}\"")
    for field in ("model", "api_key", "expires_at"):
        if not config.get(field):
            raise ValueError(f"The offer config has no \"{field}\"")
    try:
        expires_at = datetime.fromisoformat(str(config["expires_at"]))
    except ValueError as exc:
        raise ValueError(f"Bad \"expires_at\" date: {config['expires_at']}") from exc
    if expires_at.tzinfo is None:
        expires_at = expires_at.astimezone()  # a date without a zone means the user's local time
    settings = AISettings(
        provider=provider,
        model=str(config["model"]),
        base_url=str(config.get("base_url") or ""),
        api_key=str(config["api_key"]),
        expires_at=expires_at,
        share_context=share_context,
        offer=offer_id,
    )
    if settings.is_expired(now or datetime.now(timezone.utc)):
        raise ValueError("This free AI offer has ended")
    return settings
