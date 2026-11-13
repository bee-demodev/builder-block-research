"""A small Chrome DevTools Protocol client on the standard library only.

Enough to do what the live feed needs: list and open targets over HTTP, and evaluate
JavaScript in one page over a WebSocket. No third-party packages.
"""

from __future__ import annotations

import base64
import json
import os
import socket
import struct
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

HOST = "127.0.0.1"


class CdpError(Exception):
    """The debug link failed (port closed, socket dropped, a command was refused)."""


def http_json(port: int, path: str, *, method: str = "GET", timeout: float = 2.0) -> Any:
    """One call to the debug port's HTTP side. ``CdpError`` when it does not answer."""
    request = urllib.request.Request(f"http://{HOST}:{port}{path}", method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise CdpError(f"{method} {path}: {error}") from None
    try:
        return json.loads(body)
    except ValueError:
        return body  # /json/activate and /json/close answer with a sentence


def port_answers(port: int, timeout: float = 1.5) -> bool:
    try:
        http_json(port, "/json/version", timeout=timeout)
    except CdpError:
        return False
    return True


def tradingview_is_running() -> bool:
    """Whether a TradingView Desktop process exists. Looks only; never starts or stops one."""
    try:
        if sys.platform == "win32":
            done = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq TradingView.exe", "/NH", "/FO", "CSV"],
                capture_output=True, text=True, timeout=8, creationflags=0x08000000,  # no console window
            )  # fmt: skip
            return "tradingview.exe" in done.stdout.lower()
        done = subprocess.run(["pgrep", "-if", "tradingview"], capture_output=True, text=True, timeout=8)
        return bool(done.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return False


class CdpSession:
    """One WebSocket to one target. Calls are synchronous; events are ignored."""

    def __init__(self, websocket_url: str, timeout: float = 10.0) -> None:
        parts = urllib.parse.urlsplit(websocket_url)
        if parts.scheme != "ws" or not parts.hostname:
            raise CdpError(f"not a ws:// address: {websocket_url}")
        self._timeout = timeout
        self._next_id = 0
        self._buffer = b""
        port = parts.port or 80
        try:
            self._socket: socket.socket | None = socket.create_connection((parts.hostname, port), timeout=timeout)
        except OSError as error:
            raise CdpError(f"cannot connect to {websocket_url}: {error}") from None
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        path = parts.path + (f"?{parts.query}" if parts.query else "")
        # No Origin header: Chromium refuses debug sockets from pages, and takes its absence as "a tool".
        handshake = (
            f"GET {path} HTTP/1.1\r\nHost: {parts.hostname}:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n"
        )
        try:
            self._socket.sendall(handshake.encode("ascii"))
            head = b""
            while b"\r\n\r\n" not in head:
                chunk = self._socket.recv(4096)
                if not chunk:
                    raise CdpError("the debug socket closed during the handshake")
                head += chunk
        except OSError as error:
            self.close()
            raise CdpError(f"handshake failed: {error}") from None
        header, _, rest = head.partition(b"\r\n\r\n")
        if b" 101 " not in header.split(b"\r\n", 1)[0]:
            self.close()
            raise CdpError(f"the debug socket refused the connection: {header.splitlines()[0].decode('latin-1', 'replace')}")
        self._buffer = rest

    # --- frames ---

    def _read(self, count: int) -> bytes:
        if self._socket is None:
            raise CdpError("the debug socket is closed")
        while len(self._buffer) < count:
            try:
                chunk = self._socket.recv(max(65536, count - len(self._buffer)))
            except socket.timeout:
                raise CdpError("TradingView did not answer in time") from None
            except OSError as error:
                raise CdpError(f"the debug socket dropped: {error}") from None
            if not chunk:
                raise CdpError("the debug socket closed")
            self._buffer += chunk
        data, self._buffer = self._buffer[:count], self._buffer[count:]
        return data

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        if self._socket is None:
            raise CdpError("the debug socket is closed")
        mask = os.urandom(4)
        size = len(payload)
        if size < 126:
            head = struct.pack("!BB", 0x80 | opcode, 0x80 | size)
        elif size < 65536:
            head = struct.pack("!BBH", 0x80 | opcode, 0x80 | 126, size)
        else:
            head = struct.pack("!BBQ", 0x80 | opcode, 0x80 | 127, size)
        repeated = (mask * (size // 4 + 1))[:size]
        masked = (int.from_bytes(payload, "big") ^ int.from_bytes(repeated, "big")).to_bytes(size, "big") if size else b""
        try:
            self._socket.sendall(head + mask + masked)
        except OSError as error:
            raise CdpError(f"the debug socket dropped: {error}") from None

    def _receive_message(self) -> str:
        """The next complete text message; pings are answered, a close ends the session."""
        parts: list[bytes] = []
        while True:
            first, second = self._read(2)
            final, opcode, size = bool(first & 0x80), first & 0x0F, second & 0x7F
            if size == 126:
                (size,) = struct.unpack("!H", self._read(2))
            elif size == 127:
                (size,) = struct.unpack("!Q", self._read(8))
            mask = self._read(4) if second & 0x80 else b""
            payload = self._read(size)
            if mask:
                repeated = (mask * (size // 4 + 1))[:size]
                payload = (int.from_bytes(payload, "big") ^ int.from_bytes(repeated, "big")).to_bytes(size, "big") if size else b""
            if opcode == 0x8:
                self.close()
                raise CdpError("TradingView closed the debug socket")
            if opcode == 0x9:
                self._send_frame(0xA, payload)
                continue
            if opcode == 0xA:
                continue
            parts.append(payload)
            if final:
                return b"".join(parts).decode("utf-8", "replace")

    # --- commands ---

    def call(self, method: str, params: dict[str, Any] | None = None, timeout: float | None = None) -> dict[str, Any]:
        """Send one command and wait for its answer. ``CdpError`` when it is refused."""
        if self._socket is None:
            raise CdpError("the debug socket is closed")
        self._next_id += 1
        wanted = self._next_id
        self._socket.settimeout(timeout if timeout is not None else self._timeout)
        self._send_frame(0x1, json.dumps({"id": wanted, "method": method, "params": params or {}}).encode("utf-8"))
        while True:
            try:
                message = json.loads(self._receive_message())
            except ValueError:
                continue
            if message.get("id") != wanted:
                continue  # an event, or the answer to a call that timed out earlier
            if "error" in message:
                raise CdpError(f"{method}: {message['error'].get('message', message['error'])}")
            result = message.get("result")
            return result if isinstance(result, dict) else {}

    def evaluate(self, expression: str, timeout: float | None = None) -> Any:
        """Run JavaScript in the page and return its (JSON) value."""
        result = self.call("Runtime.evaluate", {"expression": expression, "returnByValue": True}, timeout)
        if "exceptionDetails" in result:
            details = result["exceptionDetails"]
            text = (details.get("exception") or {}).get("description") or details.get("text") or "JavaScript error"
            raise CdpError(f"page script failed: {str(text).splitlines()[0]}")
        return (result.get("result") or {}).get("value")

    def close(self) -> None:
        sock, self._socket = self._socket, None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

    @property
    def is_open(self) -> bool:
        return self._socket is not None
