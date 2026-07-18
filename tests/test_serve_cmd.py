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


def test_null_byte_path_is_an_honest_reject_not_a_crash(tmp_path: Path) -> None:
    # A NUL byte in the path must be refused with an HTTP status, never an
    # uncaught ValueError that drops the connection (PR#119 review fold).
    (tmp_path / "real.json").write_text("{}")
    assert _resolve_within(tmp_path, "/real.json%00.txt") is None
    assert _resolve_within(tmp_path, "/\x00") is None
    server, base = _serve(tmp_path)
    try:
        try:
            _get(f"{base}/real.json%00.txt")
            assert False, "expected an HTTP error status"
        except urllib.error.HTTPError as e:
            assert e.code in (400, 403, 404), f"got {e.code}"  # any honest status, not a crash
    finally:
        server.shutdown()


def test_directory_symlink_escape_is_refused(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.json").write_text('{"secret": true}')
    root = tmp_path / "served"
    root.mkdir()
    (root / "linkdir").symlink_to(outside)  # directory symlink out of root
    assert _resolve_within(root, "/linkdir/secret.json") is None


def test_oversize_projection_is_413(tmp_path: Path) -> None:
    from nlfr.commands.serve_cmd import MAX_PROJECTION_BYTES

    big = tmp_path / "big.json"
    big.write_text("[" + "0," * (MAX_PROJECTION_BYTES // 2) + "0]")
    assert big.stat().st_size > MAX_PROJECTION_BYTES
    server, base = _serve(tmp_path)
    try:
        try:
            _get(f"{base}/big.json")
            assert False, "expected 413"
        except urllib.error.HTTPError as e:
            assert e.code == 413
    finally:
        server.shutdown()


def test_index_skips_symlinks(tmp_path: Path) -> None:
    (tmp_path / "real.json").write_text("{}")
    outside = tmp_path / "out"
    outside.mkdir()
    (outside / "t.json").write_text("{}")
    (tmp_path / "linked.json").symlink_to(outside / "t.json")
    server, base = _serve(tmp_path)
    try:
        status, body = _get(f"{base}/")
        assert json.loads(body)["projections"] == ["real.json"], "symlink advertised"
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


def test_unreadable_projection_is_an_honest_500_not_a_dropped_connection(tmp_path: Path) -> None:
    # Fable re-review fold: read_bytes()/stat() were unguarded, so a file
    # that passes is_file() but fails to read (mode 000, or deleted between
    # checks) dropped the TCP connection — the class the honest-errors rule
    # forbids. It must be an honest status with a JSON body instead.
    import os

    if os.geteuid() == 0:  # root reads mode-000 files; the trigger needs a non-root run
        return
    doc = tmp_path / "locked.json"
    doc.write_text("{}")
    doc.chmod(0)
    server, base = _serve(tmp_path)
    try:
        try:
            status, body = _get(f"{base}/locked.json")
        except urllib.error.HTTPError as exc:  # urllib raises on 5xx; that IS a served status
            status, body = exc.code, exc.read()
        assert status == 500
        assert "not readable" in json.loads(body)["error"]
    finally:
        doc.chmod(0o644)
        server.shutdown()


def test_on_disk_index_json_is_never_listed_and_shadowing_is_disclosed(tmp_path: Path) -> None:
    # Fable re-review fold: the synthesized index shadows a real index.json;
    # listing that name would promise verbatim bytes GET cannot give. It is
    # excluded from `projections` and the shadowing disclosed instead.
    (tmp_path / "index.json").write_text(json.dumps({"real": "on-disk file"}))
    (tmp_path / "fleet.json").write_text(json.dumps({"schema": "x"}))
    server, base = _serve(tmp_path)
    try:
        status, body = _get(f"{base}/index.json")
        assert status == 200
        index = json.loads(body)
        assert index["server"] == "nlfr-serve", "route serves the synthesized index"
        assert index["projections"] == ["fleet.json"], "shadowed name is not advertised"
        assert any("index.json" in s for s in index["shadowed"])
        # Absent an on-disk index.json there is no shadowed key at all.
        (tmp_path / "index.json").unlink()
        status, body = _get(f"{base}/")
        assert "shadowed" not in json.loads(body)
    finally:
        server.shutdown()
