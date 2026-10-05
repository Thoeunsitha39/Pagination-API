import sys
import threading

from api_tool.server import tunnel as T


def _fake_provider(lines, exit_code=0):
    script = "import sys\n" + "".join(f"print({line!r}, flush=True)\n" for line in lines) + f"sys.exit({exit_code})\n"
    spec = dict(T.TUNNEL_PROVIDERS["ngrok"])
    spec.update(binary=sys.executable, command=lambda port: [sys.executable, "-c", script])
    return spec


def _run(spec, monkeypatch):
    monkeypatch.setitem(T.TUNNEL_PROVIDERS, "fake", spec)
    events, done = [], threading.Event()

    def on_event(kind, text):
        events.append((kind, text))
        if kind == "stopped":
            done.set()

    tunnel = T.Tunnel("fake", 8765, on_event)
    tunnel.start()
    assert done.wait(10)
    return tunnel, events


def test_ngrok_url_is_parsed(monkeypatch):
    spec = _fake_provider([
        '{"lvl":"info","msg":"starting web service","addr":"127.0.0.1:4040"}',
        '{"lvl":"info","msg":"started tunnel","name":"command_line","url":"https://ab12.ngrok-free.app"}',
    ])
    tunnel, events = _run(spec, monkeypatch)
    assert events[0] == ("url", "https://ab12.ngrok-free.app")
    assert tunnel.url == "https://ab12.ngrok-free.app"
    assert events[-1][0] == "stopped"


def test_ngrok_error_is_reported(monkeypatch):
    spec = _fake_provider([
        '{"lvl":"eror","msg":"session closing","err":"authentication failed: ERR_NGROK_4018"}',
    ], exit_code=1)
    _tunnel, events = _run(spec, monkeypatch)
    assert ("error", "authentication failed: ERR_NGROK_4018") in events
    assert events[-1] == ("stopped", "authentication failed: ERR_NGROK_4018")


def test_localhost_run_url_skips_admin_link(monkeypatch):
    spec = dict(T.TUNNEL_PROVIDERS["localhost.run"])
    lines = ["To set up custom domains go to https://admin.localhost.run/",
             "9b6380c0d213bb.lhr.life tunneled with tls termination, https://9b6380c0d213bb.lhr.life"]
    script = "".join(f"print({line!r}, flush=True)\n" for line in lines)
    spec.update(binary=sys.executable, command=lambda port: [sys.executable, "-c", script])
    _tunnel, events = _run(spec, monkeypatch)
    assert events[0] == ("url", "https://9b6380c0d213bb.lhr.life")


def test_missing_binary_raises(monkeypatch):
    spec = dict(T.TUNNEL_PROVIDERS["ngrok"], binary="definitely-not-installed-xyz")
    monkeypatch.setitem(T.TUNNEL_PROVIDERS, "fake", spec)
    try:
        T.Tunnel("fake", 1, lambda *a: None).start()
        assert False, "expected OSError"
    except OSError as exc:
        assert "not installed" in str(exc)


def test_lan_addresses_are_not_loopback():
    assert all(not a.startswith("127.") for a in T.lan_addresses())


def test_error_text_is_unescaped():
    assert T._clean_message("auth failed.\\n\\nSign up: https://x\\r\\n\\r\\nERR_NGROK_4018\\r\\n") == \
        "auth failed. Sign up: https://x ERR_NGROK_4018"
