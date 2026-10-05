"""Calling AI providers: Anthropic SDK, OpenAI-compatible and Gemini HTTP APIs."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from api_tool.ai.errors import AIError
from api_tool.ai.settings import CLAUDE_DEFAULT_MODEL


def _http_error_message(status, body, settings, url=""):
    detail = body
    try:
        data = json.loads(body)
        err = data.get("error") if isinstance(data, dict) else None
        if isinstance(err, dict):
            detail = err.get("message") or detail
        elif isinstance(err, str):
            detail = err
        elif isinstance(data, list) and data and isinstance(data[0], dict) and "error" in data[0]:
            detail = data[0]["error"].get("message", detail)
    except ValueError:
        pass
    detail = str(detail).strip()[:400]
    if url:
        detail = f"{detail} (called {url})".strip()
    if status in (401, 403):
        return f"The API key was rejected by {settings.label} ({status}). Check it in AI settings. {detail}"
    if status == 404:
        return (f"Model or endpoint not found ({status}). Check the model name (“Load models” lists valid ones) "
                f"and the base URL in AI settings. {detail}")
    if status == 429:
        return f"Rate limit or quota reached at {settings.label} (429). Wait a moment or check your plan. {detail}"
    return f"{settings.label} returned HTTP {status}. {detail}"


def _open(request, settings, timeout=120):
    try:
        return urlopen(request, timeout=timeout)
    except HTTPError as exc:
        raise AIError(_http_error_message(exc.code, exc.read().decode("utf-8", "replace"), settings,
                                          request.full_url)) from exc
    except (URLError, OSError, ValueError) as exc:
        raise AIError(f"Could not reach {settings.label}: {exc}") from exc


def _sse_lines(response, should_stop):
    for raw in response:
        if should_stop():
            return
        line = raw.decode("utf-8", "replace").strip()
        if line.startswith("data:"):
            yield line[5:].strip()


def _anthropic_client(settings):
    try:
        import anthropic
    except ImportError as exc:
        raise AIError("The 'anthropic' package is missing. Run: venv/bin/python -m pip install anthropic") from exc
    options = dict(api_key=settings.api_key, timeout=300.0, max_retries=2)
    if not settings.is_official_anthropic:
        # Anthropic-compatible third-party server; the SDK appends /v1/messages.
        options["base_url"] = settings.effective_base_url()
    return anthropic, anthropic.Anthropic(**options)


def _anthropic_error(anthropic, exc, settings):
    name = settings.label
    url = ""
    response = getattr(exc, "response", None)
    if response is not None and getattr(response, "request", None) is not None:
        url = f" (called {response.request.url})"
    if isinstance(exc, anthropic.AuthenticationError):
        return f"The API key was rejected by {name} (401). Check it in AI settings.{url}"
    if isinstance(exc, anthropic.PermissionDeniedError):
        return f"This {name} API key lacks permission for that model (403).{url}"
    if isinstance(exc, anthropic.NotFoundError):
        return (f"Model or endpoint not found (404) at {name}. Check the model name (“Load models” "
                f"lists valid ones) and the base URL in AI settings.{url}")
    if isinstance(exc, anthropic.RateLimitError):
        return f"{name} rate limit reached (429). Wait a moment and try again."
    if isinstance(exc, anthropic.APIStatusError):
        return f"{name} API error ({exc.status_code}): {exc.message}{url}"
    if isinstance(exc, anthropic.APIConnectionError):
        return f"Could not reach {name}. Check your internet connection and the base URL."
    return f"{type(exc).__name__}: {exc}"


def stream_chat(settings, system, messages, on_delta, should_stop=lambda: False):
    """Stream one assistant reply. Calls on_delta(text) per chunk; returns the full text."""
    if settings.wire == "anthropic":
        return _stream_anthropic(settings, system, messages, on_delta, should_stop)
    if settings.wire == "gemini":
        return _stream_gemini(settings, system, messages, on_delta, should_stop)
    return _stream_openai(settings, system, messages, on_delta, should_stop)


def _stream_anthropic(settings, system, messages, on_delta, should_stop):
    anthropic, client = _anthropic_client(settings)
    parts = []
    params = dict(model=settings.model, max_tokens=16000, system=system, messages=messages)
    if settings.is_official_anthropic:
        # Claude-only options; Anthropic-compatible third-party servers may reject them.
        params.update(cache_control={"type": "ephemeral"}, output_config={"effort": "medium"})
    if settings.is_official_anthropic and settings.model == CLAUDE_DEFAULT_MODEL:
        # Server-side safety fallback: a declined request is re-run on Anthropic's
        # recommended model inside the same call.
        params.update(betas=["server-side-fallback-2026-07-01"], fallbacks="default")
    try:
        # The beta endpoint is only needed for the fallback beta; third-party
        # Anthropic-compatible servers may not accept its ?beta=true URL.
        messages_api = client.beta.messages if "betas" in params else client.messages
        with messages_api.stream(**params) as stream:
            for text in stream.text_stream:
                if should_stop():
                    return "".join(parts)
                parts.append(text)
                on_delta(text)
            final = stream.get_final_message()
    except anthropic.APIError as exc:
        raise AIError(_anthropic_error(anthropic, exc, settings)) from exc
    if final.stop_reason == "refusal":
        note = "\n\n_(The model declined to answer this request.)_"
        parts.append(note)
        on_delta(note)
    elif final.stop_reason == "max_tokens":
        note = "\n\n_(Answer cut off at the length limit — ask me to continue.)_"
        parts.append(note)
        on_delta(note)
    return "".join(parts)


def _stream_openai(settings, system, messages, on_delta, should_stop):
    body = {
        "model": settings.model,
        "stream": True,
        "messages": [{"role": "system", "content": system}] + messages,
    }
    headers = {"Content-Type": "application/json"}
    if settings.api_key:
        headers["Authorization"] = f"Bearer {settings.api_key}"
    request = Request(f"{settings.effective_base_url()}/chat/completions",
                      data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
    parts = []
    with _open(request, settings) as response:
        for data in _sse_lines(response, should_stop):
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except ValueError:
                continue
            if chunk.get("error"):
                raise AIError(_http_error_message(500, json.dumps(chunk), settings))
            for choice in chunk.get("choices") or []:
                text = (choice.get("delta") or {}).get("content")
                if text:
                    parts.append(text)
                    on_delta(text)
    return "".join(parts)


def _stream_gemini(settings, system, messages, on_delta, should_stop):
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [
            {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
            for m in messages
        ],
    }
    model = settings.model if settings.model.startswith("models/") else f"models/{settings.model}"
    request = Request(
        f"{settings.effective_base_url()}/{model}:streamGenerateContent?alt=sse",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": settings.api_key},
        method="POST",
    )
    parts = []
    with _open(request, settings) as response:
        for data in _sse_lines(response, should_stop):
            try:
                chunk = json.loads(data)
            except ValueError:
                continue
            for candidate in chunk.get("candidates") or []:
                for part in (candidate.get("content") or {}).get("parts") or []:
                    text = part.get("text")
                    if text:
                        parts.append(text)
                        on_delta(text)
    return "".join(parts)


def list_models(settings):
    """Model IDs the key can use, newest/most relevant first where the API says so."""
    if settings.wire == "anthropic":
        anthropic, client = _anthropic_client(settings)
        try:
            return [model.id for model in client.models.list()]
        except anthropic.NotFoundError as exc:
            if settings.is_official_anthropic:
                raise AIError(_anthropic_error(anthropic, exc, settings)) from exc
            raise AIError(f"{settings.label} doesn't list its models here — type the model name "
                          "from the provider's docs instead.") from exc
        except anthropic.APIError as exc:
            raise AIError(_anthropic_error(anthropic, exc, settings)) from exc
    if settings.wire == "gemini":
        request = Request(f"{settings.effective_base_url()}/models?pageSize=200",
                          headers={"x-goog-api-key": settings.api_key})
        with _open(request, settings, timeout=30) as response:
            data = json.loads(response.read())
        return [
            m["name"].removeprefix("models/")
            for m in data.get("models", [])
            if "generateContent" in (m.get("supportedGenerationMethods") or [])
        ]
    headers = {"Authorization": f"Bearer {settings.api_key}"} if settings.api_key else {}
    request = Request(f"{settings.effective_base_url()}/models", headers=headers)
    with _open(request, settings, timeout=30) as response:
        data = json.loads(response.read())
    return sorted(m["id"] for m in data.get("data", []) if m.get("id"))
