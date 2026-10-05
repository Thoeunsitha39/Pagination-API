import json
import os
import stat
from datetime import datetime, timedelta, timezone

from api_tool.ai import (
    AISettings,
    expiry_from_choice,
    extract_stub_blocks,
    forget_key,
    load_settings,
    save_settings,
    tool_state_block,
)

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=timezone.utc)


def test_expiry_choices():
    assert expiry_from_choice("1 hour", NOW) == (NOW + timedelta(hours=1), False)
    assert expiry_from_choice("Forever (until I remove it)", NOW) == (None, False)
    assert expiry_from_choice("This session only (not saved)", NOW) == (None, True)


def test_expiry_text_and_state():
    s = AISettings(api_key="sk-test-123456", expires_at=NOW + timedelta(days=6, hours=3))
    assert s.expiry_text(NOW) == "key expires in 6d 3h"
    assert s.is_configured(NOW)
    assert not s.is_configured(NOW + timedelta(days=7))
    assert AISettings(api_key="k").expiry_text() == "key never expires"
    assert s.masked_key() == "sk-t…3456"


def test_save_is_private_and_session_keys_never_written(tmp_path):
    path = str(tmp_path / "ai.json")
    save_settings(AISettings(api_key="secret-key-1", expires_at=None), path)
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert load_settings(path).api_key == "secret-key-1"
    save_settings(AISettings(api_key="secret-key-2", session_only=True), path)
    assert "secret-key-2" not in open(path).read()


def test_expired_key_is_removed_on_load(tmp_path):
    path = str(tmp_path / "ai.json")
    save_settings(AISettings(provider="openai", model="m", api_key="old-key",
                             expires_at=datetime.now(timezone.utc) - timedelta(minutes=1)), path)
    loaded = load_settings(path)
    assert loaded.api_key == "" and loaded.provider == "openai" and loaded.model == "m"
    assert "old-key" not in open(path).read()


def test_forget_key_keeps_choices(tmp_path):
    path = str(tmp_path / "ai.json")
    cleared = forget_key(AISettings(provider="groq", model="x", api_key="k"), path)
    assert (cleared.provider, cleared.model, cleared.api_key) == ("groq", "x", "")


def test_ollama_needs_no_key():
    assert AISettings(provider="ollama", model="llama").is_configured()
    assert not AISettings(provider="openai", model="m").is_configured()


def test_extract_stub_blocks():
    answer = (
        "Here is a fix:\n```json\n"
        + json.dumps({"mappings": [{"name": "Fixed", "request": {"method": "GET", "urlPath": "/a"},
                                    "response": {"status": 200}}]})
        + "\n```\nand some other code:\n```json\n{\"not\": \"a stub\"}\n```\n"
    )
    (stub,) = extract_stub_blocks(answer)
    assert stub["name"] == "Fixed" and stub["request"]["urlPath"] == "/a"
    assert extract_stub_blocks("no code here") == []


def test_tool_state_block_has_no_secrets_and_summarizes_log():
    block = tool_state_block(
        "http://127.0.0.1:8765 (Basic Auth: on)",
        [{"name": "Hello", "request": {"method": "GET"}, "response": {}}],
        "Hello",
        [{"time": "10:00:00", "method": "PUT", "path": "/api/hello", "status": 404, "matched": None,
          "payload": {"detail": "No stub matched this request", "disabledMatches": ["Hello"]}}],
    )
    assert "PUT /api/hello -> 404" in block and "disabledMatches=['Hello']" in block
    assert '"name": "Hello"' in block


def test_wire_format_detection():
    assert AISettings(provider="deepseek", model="m", base_url="https://api.deepseek.com/anthropic").wire == "anthropic"
    assert AISettings(provider="deepseek", model="m", base_url="https://api.deepseek.com/anthropic/").wire == "anthropic"
    assert AISettings(provider="deepseek", model="m").wire == "openai"
    assert AISettings(provider="anthropic_compat", model="m", base_url="https://x/anthropic").wire == "anthropic"
    official = AISettings(provider="anthropic", model="m", api_key="k")
    assert official.wire == "anthropic" and official.is_official_anthropic and official.is_configured()
    assert not AISettings(provider="anthropic_compat", model="m", api_key="k").is_configured()  # needs a base URL


def test_extract_python_block_and_logic_messages():
    from api_tool.ai import extract_python_block, logic_request_messages

    code, explanation = extract_python_block(
        "Returns 404 for big ids.\n```python\nif int(request.path_segments[-1]) > 100:\n    response.status = 404\n```\nDone."
    )
    assert code == "if int(request.path_segments[-1]) > 100:\n    response.status = 404\n"
    assert explanation == "Returns 404 for big ids.\n\nDone."
    assert extract_python_block("no code") == (None, "no code")
    (message,) = logic_request_messages("404 when id > 100", {"id": "x", "name": "Get"}, "")
    assert "404 when id > 100" in message["content"] and '"name": "Get"' in message["content"]
    assert '"id": "x"' not in message["content"]
