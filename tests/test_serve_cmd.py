"""NB.1: the read-only projection server (stdlib-only)."""

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from nlfr.commands.serve_cmd import _resolve_within, make_handler


def _serve(tmp_path: Path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(tmp_path))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    return server, f"http://{host}:{port}"


def _get(url: str):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return resp.status, resp.read()


def test_serves_exported_projections_verbatim(tmp_path: Path) -> None:
    doc = {"schema": "nlfr.fleet_projection.v1", "runs": 3}
    (tmp_path / "fleet.json").write_text(json.dumps(doc))
    (tmp_path / "notes.txt").write_text("not a projection")
    server, base = _serve(tmp_path)
    try:
        # Index lists only .json files, never the .txt.
        status, body = _get(f"{base}/")
        assert status == 200
        index = json.loads(body)
        assert index["projections"] == ["fleet.json"]
        # The projection is served byte-for-byte.
        status, body = _get(f"{base}/fleet.json")
        assert status == 200
        assert json.loads(body) == doc
    finally:
        server.shutdown()


def test_path_traversal_stays_within_root(tmp_path: Path) -> None:
    # Safety invariant: for ANY hostile url path, the resolved target is
    # either None or strictly within root — never outside. (`..` segments are
    # collapsed against the leading `/` by normpath, so they land back inside
    # root rather than escaping — still safe.)
    root = tmp_path
    root_resolved = root.resolve()
    for hostile in ["/../etc/passwd", "/a/../../etc", "/../../..", "/./x", "//y", "/%2e%2e/z"]:
        result = _resolve_within(root, hostile)
        assert result is None or result == root_resolved or root_resolved in result.parents, (
            f"{hostile!r} resolved to {result} — outside root"
        )
    assert _resolve_within(root, "/fleet.json") == (root / "fleet.json").resolve()
    assert _resolve_within(root, "/") == root_resolved


def test_symlink_escape_is_refused(tmp_path: Path) -> None:
    # A symlink inside root pointing OUTSIDE it must not let a request read
    # the target — the resolve()+parents check catches it.
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.json").write_text('{"secret": true}')
    root = tmp_path / "served"
    root.mkdir()
    (root / "escape.json").symlink_to(outside / "secret.json")
    assert _resolve_within(root, "/escape.json") is None


def test_non_json_and_missing_are_honest_errors(tmp_path: Path) -> None:
    server, base = _serve(tmp_path)
    try:
        # A .txt request → 404 (only .json served).
        try:
            _get(f"{base}/notes.txt")
            assert False, "expected 404"
        except urllib.error.HTTPError as e:
            assert e.code == 404
        # Missing projection → 404.
        try:
            _get(f"{base}/nope.json")
            assert False, "expected 404"
        except urllib.error.HTTPError as e:
            assert e.code == 404
    finally:
        server.shutdown()


def test_corrupt_projection_is_a_500_not_silently_served(tmp_path: Path) -> None:
    (tmp_path / "broken.json").write_text("{not valid json")
    server, base = _serve(tmp_path)
    try:
        try:
            _get(f"{base}/broken.json")
            assert False, "expected 500"
        except urllib.error.HTTPError as e:
            assert e.code == 500
    finally:
        server.shutdown()


def test_write_methods_are_rejected(tmp_path: Path) -> None:
    (tmp_path / "fleet.json").write_text("{}")
    server, base = _serve(tmp_path)
    try:
        req = urllib.request.Request(f"{base}/fleet.json", method="POST", data=b"x")
        try:
            urllib.request.urlopen(req, timeout=5)
            assert False, "expected 405"
        except urllib.error.HTTPError as e:
            assert e.code == 405
    finally:
        server.shutdown()
