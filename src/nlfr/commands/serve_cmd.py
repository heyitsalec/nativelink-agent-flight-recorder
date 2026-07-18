"""Local projection server (stdlib-only).

Serves exported projection JSON from a directory over HTTP for local
inspection and for GUI consumers (the canvas). Read-only by construction:
GET only, no write methods, no state invented — it serves exactly the bytes
on disk under the served root and nothing else. Path traversal is refused;
only ``.json`` files (and a directory index of them) are exposed.
"""

from __future__ import annotations

import argparse
import json
import posixpath
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


def _resolve_within(root: Path, url_path: str) -> Path | None:
    """Resolve a URL path under ``root``, or ``None`` if it escapes it."""
    # Normalize the percent-decoded POSIX path, strip leading slashes, and
    # reject any component that would climb out of root.
    decoded = unquote(url_path)
    if "\x00" in decoded:
        return None  # embedded NUL — reject before it reaches the filesystem
    normalized = posixpath.normpath(decoded).lstrip("/")
    try:
        if normalized in ("", "."):
            return root.resolve()
        candidate = (root / normalized).resolve()
        root_resolved = root.resolve()
    except (ValueError, OSError):
        # Any path the OS refuses to stat (NUL, too long, bad bytes) is an
        # honest rejection, never an uncaught crash (PR#119 review fold).
        return None
    if candidate == root_resolved or root_resolved in candidate.parents:
        return candidate
    return None


# Local dev tool: cap the served file size so a giant file can't exhaust
# memory. Projections are small (KBs–low MBs); 64 MiB is generous.
MAX_PROJECTION_BYTES = 64 * 1024 * 1024


def make_handler(root: Path) -> type[BaseHTTPRequestHandler]:
    class ProjectionHandler(BaseHTTPRequestHandler):
        server_version = "nlfr-serve/1"

        def _send_json(self, code: int, payload: object) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            # Read-only surface: never cache stale evidence in a proxy.
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _reject(self, code: int, detail: str) -> None:
            self._send_json(code, {"error": detail})

        def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
            path = urlparse(self.path).path
            if path == "/" or path == "/index.json":
                # Only real files (not symlinks, which would 403 on fetch)
                # so the listing never advertises an unservable name. A real
                # on-disk index.json is excluded too: this route shadows it,
                # so listing it would promise verbatim bytes GET can't give —
                # the shadowing is disclosed instead of papered over.
                names = sorted(
                    p.name
                    for p in root.iterdir()
                    if p.is_file()
                    and not p.is_symlink()
                    and p.suffix == ".json"
                    and p.name != "index.json"
                )
                payload: dict[str, object] = {
                    "server": "nlfr-serve",
                    "projections": names,
                    "note": (
                        "this index is server-synthesized metadata; the projection "
                        "FILES it lists are served byte-for-byte and invent no state"
                    ),
                }
                if (root / "index.json").is_file():
                    payload["shadowed"] = [
                        "index.json (an on-disk file of this name exists but cannot be "
                        "served verbatim at this route; rename it to serve it)"
                    ]
                self._send_json(200, payload)
                return
            target = _resolve_within(root, path)
            if target is None:
                self._reject(403, "path escapes the served root")
                return
            if target.suffix != ".json":
                self._reject(404, "only .json projections are served")
                return
            # The stat/read pair is guarded: an unreadable file (mode 000,
            # foreign-owned) or one deleted between checks (TOCTOU) must be
            # an honest status, never a dropped connection — the same
            # honest-errors rule the resolver already follows.
            try:
                if not target.is_file():
                    self._reject(404, "no such projection")
                    return
                if target.stat().st_size > MAX_PROJECTION_BYTES:
                    self._reject(413, "projection exceeds the served size cap")
                    return
                # Serve the exact bytes; validate it is JSON so a corrupt file
                # is an honest 500, never silently served as something else.
                raw = target.read_bytes()
            except FileNotFoundError:
                self._reject(404, "no such projection")
                return
            except OSError as exc:
                self._reject(500, f"projection is not readable: {exc.__class__.__name__}")
                return
            try:
                json.loads(raw)
            except json.JSONDecodeError as exc:
                self._reject(500, f"projection is not valid JSON: {exc}")
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(raw)

        do_HEAD = do_GET  # noqa: N815

        def do_POST(self) -> None:  # noqa: N802
            self._reject(405, "read-only server: POST is not allowed")

        do_PUT = do_POST  # noqa: N815
        do_DELETE = do_POST  # noqa: N815

        def log_message(self, *args: object) -> None:  # silence default logging
            return

    return ProjectionHandler


def run(args: argparse.Namespace) -> int:
    root = Path(args.dir).resolve()
    if not root.is_dir():
        print(f"nlfr serve: {root} is not a directory", flush=True)
        return 1
    handler = make_handler(root)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    bound_host, bound_port = server.server_address[:2]
    print(
        f"nlfr serve: read-only projection server on http://{bound_host}:{bound_port} "
        f"serving {root} ({len(list(root.glob('*.json')))} projections)",
        flush=True,
    )
    if str(bound_host) not in ("127.0.0.1", "::1", "localhost"):
        print(
            "nlfr serve: WARNING — bound to a non-loopback interface; projections "
            "(which can carry paths and evidence) are served with NO authentication "
            "to anyone who can reach this address.",
            flush=True,
        )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``serve`` command on ``subparsers``."""

    parser = subparsers.add_parser(
        "serve",
        help="serve exported projection JSON locally (read-only)",
        description="Serve exported projection JSON locally over HTTP. Read-only, stdlib-only.",
    )
    parser.add_argument(
        "--dir",
        default="projections",
        help="directory of exported .json projections to serve (default: projections)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="bind host (default loopback; a non-loopback host serves projections UNAUTHENTICATED)",
    )
    parser.add_argument("--port", type=int, default=8080, help="bind port")
    parser.set_defaults(handler=run)
