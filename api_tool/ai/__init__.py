"""AI assistant: provider settings, API-key expiry, streaming chat, and the tool guide.

Claude goes through the official `anthropic` SDK. OpenAI, Google Gemini and
OpenAI-compatible services (OpenRouter, Groq, DeepSeek, Mistral, xAI, Ollama,
or any custom base URL) use their own HTTP APIs via urllib.

Settings live in <config>/api-tool/ai.json with owner-only permissions. A key
can be kept for a fixed time, forever, or only for this session (never written).
"""

from api_tool.ai.errors import (  # noqa: F401
    AIError,
)

from api_tool.ai.prompts import (  # noqa: F401
    MAX_HISTORY_MESSAGES,
    MAX_CONTEXT_CHARS,
    TOOL_GUIDE,
    ASSISTANT_INSTRUCTIONS,
    system_prompt,
    tool_state_block,
    extract_stub_blocks,
    LOGIC_GENERATOR_INSTRUCTIONS,
    logic_request_messages,
    extract_python_block,
)

from api_tool.ai.providers import (  # noqa: F401
    stream_chat,
    list_models,
)

from api_tool.ai.settings import (  # noqa: F401
    CLAUDE_DEFAULT_MODEL,
    PROVIDERS,
    KEY_LIFETIMES,
    settings_path,
    AISettings,
    load_settings,
    save_settings,
    forget_key,
    expiry_from_choice,
)


__all__ = [
    "AIError",
    "MAX_HISTORY_MESSAGES",
    "MAX_CONTEXT_CHARS",
    "TOOL_GUIDE",
    "ASSISTANT_INSTRUCTIONS",
    "system_prompt",
    "tool_state_block",
    "extract_stub_blocks",
    "LOGIC_GENERATOR_INSTRUCTIONS",
    "logic_request_messages",
    "extract_python_block",
    "stream_chat",
    "list_models",
    "CLAUDE_DEFAULT_MODEL",
    "PROVIDERS",
    "KEY_LIFETIMES",
    "settings_path",
    "AISettings",
    "load_settings",
    "save_settings",
    "forget_key",
    "expiry_from_choice",
]
