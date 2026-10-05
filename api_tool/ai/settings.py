"""AI provider settings and API-key storage with expiry."""

import json
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from api_tool.core.private_file import write_private_json


CLAUDE_DEFAULT_MODEL = "claude-opus-5-5"


# key -> (label, kind, default base URL, default model, needs API key)
PROVIDERS = {
    "anthropic": ("Anthropic (Claude)", "anthropic", "", CLAUDE_DEFAULT_MODEL, True),
    "openai": ("OpenAI", "openai", "https://api.openai.com/v1", "", True),
    "gemini": ("Google Gemini", "gemini", "https://generativelanguage.googleapis.com/v1beta", "", True),
    "openrouter": ("OpenRouter", "openai", "https://openrouter.ai/api/v1", "", True),
    "groq": ("Groq", "openai", "https://api.groq.com/openai/v1", "", True),
    "deepseek": ("DeepSeek", "openai", "https://api.deepseek.com/v1", "", True),
    "mistral": ("Mistral", "openai", "https://api.mistral.ai/v1", "", True),
    "xai": ("xAI (Grok)", "openai", "https://api.x.ai/v1", "", True),
    "ollama": ("Ollama (local, no key)", "openai", "http://localhost:11434/v1", "", False),
    "custom": ("Other OpenAI-compatible", "openai", "", "", False),
    "anthropic_compat": ("Other Anthropic-compatible", "anthropic", "", "", True),
}


# label -> lifetime (None = forever, "session" = never written to disk)
KEY_LIFETIMES = [
    ("1 hour", timedelta(hours=1)),
    ("8 hours", timedelta(hours=8)),
    ("1 day", timedelta(days=1)),
    ("7 days", timedelta(days=7)),
    ("30 days", timedelta(days=30)),
    ("Forever (until I remove it)", None),
    ("This session only (not saved)", "session"),
]


def settings_path():
    config_home = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(config_home, "api-tool", "ai.json")


class AISettings:
    def __init__(self, provider="anthropic", model=CLAUDE_DEFAULT_MODEL, base_url="", api_key="",
                 expires_at=None, session_only=False, share_context=True):
        self.provider = provider if provider in PROVIDERS else "anthropic"
        self.model = model
        self.base_url = base_url
        self.api_key = api_key
        self.expires_at = expires_at  # aware datetime, or None = forever
        self.session_only = session_only
        self.share_context = share_context

    @property
    def kind(self):
        return PROVIDERS[self.provider][1]

    @property
    def wire(self):
        """API format actually spoken: a base URL ending in /anthropic (e.g. DeepSeek's
        https://api.deepseek.com/anthropic) means the Anthropic Messages format."""
        if self.kind == "openai" and urlparse(self.effective_base_url()).path.rstrip("/").endswith("/anthropic"):
            return "anthropic"
        return self.kind

    @property
    def is_official_anthropic(self):
        return self.provider == "anthropic"

    @property
    def label(self):
        return PROVIDERS[self.provider][0]

    @property
    def needs_key(self):
        return PROVIDERS[self.provider][4]

    def effective_base_url(self):
        return (self.base_url or PROVIDERS[self.provider][2]).rstrip("/")

    def is_configured(self, now=None):
        if self.is_expired(now):
            return False
        if self.needs_key and not self.api_key:
            return False
        return bool(self.model) and (self.is_official_anthropic or bool(self.effective_base_url()))

    def is_expired(self, now=None):
        return self.expires_at is not None and (now or datetime.now(timezone.utc)) >= self.expires_at

    def expiry_text(self, now=None):
        if self.session_only:
            return "key kept for this session only"
        if self.expires_at is None:
            return "key never expires"
        left = self.expires_at - (now or datetime.now(timezone.utc))
        if left.total_seconds() <= 0:
            return "key expired"
        days, rest = divmod(int(left.total_seconds()), 86400)
        hours, rest = divmod(rest, 3600)
        minutes = rest // 60
        if days:
            return f"key expires in {days}d {hours}h"
        if hours:
            return f"key expires in {hours}h {minutes}m"
        return f"key expires in {max(minutes, 1)}m"

    def masked_key(self):
        if not self.api_key:
            return ""
        return f"{self.api_key[:4]}…{self.api_key[-4:]}" if len(self.api_key) > 10 else "••••"

    def to_json(self):
        return {
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "api_key": self.api_key,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "share_context": self.share_context,
        }

    @classmethod
    def from_json(cls, data):
        expires = data.get("expires_at")
        try:
            expires_at = datetime.fromisoformat(expires) if expires else None
        except ValueError:
            expires_at = datetime.now(timezone.utc)  # unreadable -> treat as expired
        return cls(
            provider=data.get("provider", "anthropic"),
            model=data.get("model") or "",
            base_url=data.get("base_url") or "",
            api_key=data.get("api_key") or "",
            expires_at=expires_at,
            share_context=data.get("share_context", True),
        )


def load_settings(path=None):
    """Saved settings, with an expired key already removed (from memory and disk)."""
    path = path or settings_path()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            settings = AISettings.from_json(json.load(fh))
    except (OSError, ValueError):
        return AISettings()
    if settings.is_expired():
        settings = forget_key(settings, path)
    return settings


def save_settings(settings, path=None):
    """Write settings readable only by this user. Session-only keys are never written."""
    path = path or settings_path()
    data = settings.to_json()
    if settings.session_only:
        data["api_key"] = ""
        data["expires_at"] = None
    write_private_json(path, data)


def forget_key(settings, path=None):
    """Remove the API key everywhere but keep provider/model choices."""
    cleared = AISettings(provider=settings.provider, model=settings.model, base_url=settings.base_url,
                         share_context=settings.share_context)
    try:
        save_settings(cleared, path)
    except OSError:
        pass
    return cleared


def expiry_from_choice(choice, now=None):
    """(expires_at, session_only) for one of the KEY_LIFETIMES labels."""
    lifetime = dict(KEY_LIFETIMES)[choice]
    if lifetime == "session":
        return None, True
    if lifetime is None:
        return None, False
    return (now or datetime.now(timezone.utc)) + lifetime, False
