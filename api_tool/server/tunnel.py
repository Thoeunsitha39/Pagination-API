"""Public URL for the mock server via a tunnel (ngrok or localhost.run), plus LAN addresses."""

import json
import re
import shutil
import socket
import subprocess
import threading

# key -> settings for one tunnel provider
TUNNEL_PROVIDERS = {
    "ngrok": {
        "label": "ngrok",
        "binary": "ngrok",
        "command": lambda port: ["ngrok", "http", str(port), "--log", "stdout", "--log-format", "json"],
        "url": re.compile(r'"url":"(https://[^"]+)"'),
        "error": re.compile(r'"lvl":"(?:eror|crit)".*?"err":"([^"]+)"'),
        "help": "Free account at ngrok.com. Run once in a terminal: ngrok config add-authtoken <your token>",
        "missing": "ngrok is not installed. Get it from https://ngrok.com/download",
    },
    "localhost.run": {
        "label": "localhost.run (SSH, no account)",
        "binary": "ssh",
        "command": lambda port: [
            "ssh", "-T",
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "ServerAliveInterval=30",
            "-o", "ExitOnForwardFailure=yes",
            "-R", f"80:localhost:{port}",
            "nokey@localhost.run",
        ],
        "url": re.compile(r"(https://[a-z0-9-]+\.lhr\.life)"),
        "error": re.compile(r"((?:Permission denied|Connection refused|Could not resolve)[^\n]*)"),
        "help": "No account needed. The address changes every time you start it.",
        "missing": "The ssh command is not installed (sudo apt install openssh-client).",
    },
}


def provider_available(key):
    return shutil.which(TUNNEL_PROVIDERS[key]["binary"]) is not None


def lan_addresses():
    """This PC's IPv4 addresses other machines on the network can use (best guess first)."""
    addresses = []
    try:
        # No packets are sent: connecting a UDP socket only picks the outgoing interface.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("10.255.255.255", 1))
            addresses.append(probe.getsockname()[0])
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = info[4][0]
            if address not in addresses:
                addresses.append(address)
    except OSError:
        pass
    return [a for a in addresses if not a.startswith("127.")]


def _clean_message(text):
    """Turn JSON-escaped log text (ngrok) into readable text on one line."""
    try:
        text = json.loads(f'"{text}"')
    except ValueError:
        pass
    return " ".join(text.split())


class Tunnel:
    """Runs a tunnel process in the background and reports events.

    on_event(kind, text) is called from a background thread with kind:
      "url"     – the public https URL is ready
      "error"   – the provider reported a problem
      "stopped" – the process ended (text = last error or output line)
    """

    def __init__(self, provider, port, on_event):
        self.provider = provider
        self.port = port
        self.on_event = on_event
        self.url = None
        self.process = None
        self._stopping = False
        self._last_error = ""
        self._last_line = ""

    @property
    def running(self):
        return self.process is not None and self.process.poll() is None

    def start(self):
        spec = TUNNEL_PROVIDERS[self.provider]
        if not provider_available(self.provider):
            raise OSError(spec["missing"])
        self.process = subprocess.Popen(
            spec["command"](self.port),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            start_new_session=True,  # Ctrl+C in the terminal doesn't kill it behind our back
        )
        threading.Thread(target=self._read_output, daemon=True).start()

    def _read_output(self):
        spec = TUNNEL_PROVIDERS[self.provider]
        for line in self.process.stdout:
            line = line.strip()
            if not line:
                continue
            self._last_line = line[:300]
            if self.url is None:
                match = spec["url"].search(line)
                if match and "admin.localhost.run" not in match.group(1):
                    self.url = match.group(1)
                    self.on_event("url", self.url)
                    continue
            error = spec["error"].search(line)
            if error:
                self._last_error = _clean_message(error.group(1))
                self.on_event("error", self._last_error)
        self.process.wait()
        if not self._stopping:
            self.on_event("stopped", self._last_error or self._last_line or "The tunnel process ended.")

    def stop(self):
        self._stopping = True
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.url = None
