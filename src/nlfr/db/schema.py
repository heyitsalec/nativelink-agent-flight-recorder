"""SQLite schema and migration helpers for the NLFR data spine."""

from __future__ import annotations

from dataclasses import dataclass
from sqlite3 import Connection

SCHEMA_VERSION = 3

CORE_TABLES = (
    "runs",
    "changes",
    "invocations",
    "artifacts",
    "artifact_references",
    "targets",
    "actions",
    "cache_events",
    "failures",
    "graph_nodes",
    "graph_edges",
    "proof_blocks",
)

_SOURCE_KIND_CHECK = (
    "source_kind IS NULL OR source_kind IN "
    "('collectable_v1','derived_v1','simulated_v1','future')"
)
_CONFIDENCE_CHECK = "confidence IN ('high','medium','low','unknown')"
_REDACTION_STATE_CHECK = "redaction_state IN ('safe','redacted','blocked','unknown')"

_COMMON_COLUMNS = f"""
    source_kind TEXT CHECK ({_SOURCE_KIND_CHECK}),
    confidence TEXT NOT NULL DEFAULT 'unknown' CHECK ({_CONFIDENCE_CHECK}),
    evidence_refs TEXT NOT NULL DEFAULT '[]',
    redaction_state TEXT NOT NULL DEFAULT 'unknown' CHECK ({_REDACTION_STATE_CHECK}),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
"""

_CREATE_CORE_SCHEMA = f"""
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    stable_key TEXT NOT NULL UNIQUE,
    run_group TEXT,
    scenario TEXT,
    mode TEXT,
    status TEXT,
    started_at TEXT,
    ended_at TEXT,
{_COMMON_COLUMNS}
);

CREATE TABLE IF NOT EXISTS changes (
    id TEXT PRIMARY KEY,
    stable_key TEXT NOT NULL UNIQUE,
    run_id TEXT REFERENCES runs(id) ON DELETE CASCADE,
    change_kind TEXT,
    path TEXT,
    before_hash TEXT,
    after_hash TEXT,
    summary TEXT,
{_COMMON_COLUMNS}
);

CREATE TABLE IF NOT EXISTS invocations (
    id TEXT PRIMARY KEY,
    stable_key TEXT NOT NULL UNIQUE,
    run_id TEXT REFERENCES runs(id) ON DELETE CASCADE,
    invocation_kind TEXT,
    command TEXT,
    cwd TEXT,
    env_hash TEXT,
    exit_code INTEGER,
    started_at TEXT,
    ended_at TEXT,
{_COMMON_COLUMNS}
);

CREATE TABLE IF NOT EXISTS artifacts (
    id TEXT PRIMARY KEY,
    stable_key TEXT NOT NULL UNIQUE,
    run_id TEXT REFERENCES runs(id) ON DELETE CASCADE,
    artifact_key TEXT NOT NULL,
    artifact_path TEXT NOT NULL,
    manifest_path TEXT,
    sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    content_type TEXT,
    producer_command TEXT NOT NULL,
    config_hash TEXT,
{_COMMON_COLUMNS},
    UNIQUE(run_id, artifact_key)
);

CREATE TABLE IF NOT EXISTS targets (
    id TEXT PRIMARY KEY,
    stable_key TEXT NOT NULL UNIQUE,
    run_id TEXT REFERENCES runs(id) ON DELETE CASCADE,
    label TEXT NOT NULL,
    target_kind TEXT,
    status TEXT,
{_COMMON_COLUMNS},
    UNIQUE(run_id, label)
);

CREATE TABLE IF NOT EXISTS actions (
    id TEXT PRIMARY KEY,
    stable_key TEXT NOT NULL UNIQUE,
    run_id TEXT REFERENCES runs(id) ON DELETE CASCADE,
    target_id TEXT REFERENCES targets(id) ON DELETE SET NULL,
    action_key TEXT NOT NULL,
    mnemonic TEXT,
    status TEXT,
{_COMMON_COLUMNS},
    UNIQUE(run_id, action_key)
);

CREATE TABLE IF NOT EXISTS cache_events (
    id TEXT PRIMARY KEY,
    stable_key TEXT NOT NULL UNIQUE,
    run_id TEXT REFERENCES runs(id) ON DELETE CASCADE,
    target_id TEXT REFERENCES targets(id) ON DELETE SET NULL,
    action_id TEXT REFERENCES actions(id) ON DELETE SET NULL,
    event_key TEXT,
    event_kind TEXT,
    hit INTEGER CHECK (hit IS NULL OR hit IN (0, 1)),
    digest TEXT,
{_COMMON_COLUMNS}
);

CREATE TABLE IF NOT EXISTS failures (
    id TEXT PRIMARY KEY,
    stable_key TEXT NOT NULL UNIQUE,
    run_id TEXT REFERENCES runs(id) ON DELETE CASCADE,
    failure_kind TEXT,
    message TEXT,
    span TEXT,
{_COMMON_COLUMNS}
);

CREATE TABLE IF NOT EXISTS graph_nodes (
    id TEXT PRIMARY KEY,
    stable_key TEXT NOT NULL UNIQUE,
    run_id TEXT REFERENCES runs(id) ON DELETE CASCADE,
    node_key TEXT NOT NULL,
    node_kind TEXT NOT NULL,
    label TEXT,
    payload TEXT,
{_COMMON_COLUMNS},
    UNIQUE(run_id, node_key)
);

CREATE TABLE IF NOT EXISTS graph_edges (
    id TEXT PRIMARY KEY,
    stable_key TEXT NOT NULL UNIQUE,
    run_id TEXT REFERENCES runs(id) ON DELETE CASCADE,
    from_node_id TEXT REFERENCES graph_nodes(id) ON DELETE SET NULL,
    to_node_id TEXT REFERENCES graph_nodes(id) ON DELETE SET NULL,
    from_node_key TEXT NOT NULL,
    to_node_key TEXT NOT NULL,
    edge_kind TEXT NOT NULL,
    payload TEXT,
{_COMMON_COLUMNS},
    UNIQUE(run_id, from_node_key, to_node_key, edge_kind)
);

CREATE TABLE IF NOT EXISTS proof_blocks (
    id TEXT PRIMARY KEY,
    stable_key TEXT NOT NULL UNIQUE,
    run_id TEXT REFERENCES runs(id) ON DELETE CASCADE,
    block_key TEXT NOT NULL,
    block_kind TEXT NOT NULL,
    title TEXT,
    summary TEXT,
    payload TEXT,
{_COMMON_COLUMNS},
    UNIQUE(run_id, block_key)
);

CREATE INDEX IF NOT EXISTS idx_changes_run_id ON changes(run_id);
CREATE INDEX IF NOT EXISTS idx_invocations_run_id ON invocations(run_id);
CREATE INDEX IF NOT EXISTS idx_artifacts_run_id ON artifacts(run_id);
CREATE INDEX IF NOT EXISTS idx_targets_run_id ON targets(run_id);
CREATE INDEX IF NOT EXISTS idx_actions_run_id ON actions(run_id);
CREATE INDEX IF NOT EXISTS idx_cache_events_run_id ON cache_events(run_id);
CREATE INDEX IF NOT EXISTS idx_failures_run_id ON failures(run_id);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_run_id ON graph_nodes(run_id);
CREATE INDEX IF NOT EXISTS idx_graph_edges_run_id ON graph_edges(run_id);
CREATE INDEX IF NOT EXISTS idx_proof_blocks_run_id ON proof_blocks(run_id);
"""

# The presence vocabulary shipped in v2 (schema version 2). Kept verbatim so any
# database stamped user_version=2 was created against EXACTLY this CHECK; v3 is
# what widens it. Never edit a shipped migration's SQL in place — migrate() skips
# a migration whose version a DB already has, and CREATE TABLE IF NOT EXISTS is a
# no-op, so an in-place widening silently never reaches an existing v2 database.
_PRESENCE_CHECK_V2 = (
    "presence IS NULL OR presence IN "
    "('local_verified','local_mismatch','missing','unverified_remote_reference')"
)

# v3 adds 'local_present': bytes are on disk (or a symlink target / inlined bytes
# exist) but the BEP-declared digest was NOT cross-checked as SHA-256, so presence
# is recorded without a verified digest. SQLite cannot ALTER a CHECK constraint, so
# v3 widens it by rebuilding the table (create new -> copy rows -> drop -> rename).
_PRESENCE_CHECK_V3 = (
    "presence IS NULL OR presence IN "
    "('local_verified','local_present','local_mismatch','missing',"
    "'unverified_remote_reference')"
)


def _artifact_references_columns(presence_check: str) -> str:
    """Column definitions for ``artifact_references``, parameterized by presence CHECK.

    Shared by the v2 create and the v3 rebuild so the two table definitions cannot
    drift apart in anything but the presence CHECK.
    """

    return f"""
    id TEXT PRIMARY KEY,
    stable_key TEXT NOT NULL UNIQUE,
    run_id TEXT REFERENCES runs(id) ON DELETE CASCADE,
    target_id TEXT REFERENCES targets(id) ON DELETE SET NULL,
    reference_key TEXT NOT NULL,
    name TEXT,
    uri TEXT,
    local_path TEXT,
    declared_digest TEXT,
    declared_size_bytes INTEGER,
    computed_digest TEXT,
    digest_verified INTEGER CHECK (digest_verified IS NULL OR digest_verified IN (0, 1)),
    presence TEXT CHECK ({presence_check}),
    verification_note TEXT,
{_COMMON_COLUMNS},
    UNIQUE(run_id, reference_key)
"""


# Non-key columns copied during the v3 rebuild, in a stable explicit order (never
# ``SELECT *``, which would silently mis-map if the column order ever changes).
_ARTIFACT_REFERENCE_COPY_COLUMNS = (
    "id, stable_key, run_id, target_id, reference_key, name, uri, local_path, "
    "declared_digest, declared_size_bytes, computed_digest, digest_verified, "
    "presence, verification_note, source_kind, confidence, evidence_refs, "
    "redaction_state, created_at, updated_at"
)

_CREATE_ARTIFACT_REFERENCES = f"""
CREATE TABLE IF NOT EXISTS artifact_references (
{_artifact_references_columns(_PRESENCE_CHECK_V2)}
);

CREATE INDEX IF NOT EXISTS idx_artifact_references_run_id ON artifact_references(run_id);
"""

# v3: widen the presence CHECK by table rebuild. artifact_references is a leaf (no
# other table references it), so the drop/rename is safe with foreign_keys ON. The
# leading DROP ... IF EXISTS clears any temp table left by a prior interrupted run.
_WIDEN_ARTIFACT_REFERENCES_PRESENCE = f"""
DROP TABLE IF EXISTS artifact_references_v3_rebuild;

CREATE TABLE artifact_references_v3_rebuild (
{_artifact_references_columns(_PRESENCE_CHECK_V3)}
);

INSERT INTO artifact_references_v3_rebuild ({_ARTIFACT_REFERENCE_COPY_COLUMNS})
SELECT {_ARTIFACT_REFERENCE_COPY_COLUMNS}
FROM artifact_references;

DROP TABLE artifact_references;
ALTER TABLE artifact_references_v3_rebuild RENAME TO artifact_references;

CREATE INDEX IF NOT EXISTS idx_artifact_references_run_id ON artifact_references(run_id);
"""


@dataclass(frozen=True)
class Migration:
    version: int
    sql: str


def atomic_migration_script(migration: Migration) -> str:
    """One migration as a single explicit transaction, version stamp included.

    ``executescript()`` provides no atomicity across its statements, and a
    surrounding connection context manager cannot roll back work the script
    already committed — an interruption mid-way through the v3 table rebuild
    (between ``DROP TABLE artifact_references`` and the rename) would
    otherwise lose the table permanently, with the replay destroying the
    copied rows in the temp table. ``BEGIN IMMEDIATE`` plus stamping
    ``user_version`` inside the same transaction makes each migration
    all-or-nothing: either the schema change AND its version stamp land
    together, or neither does.
    """

    return (
        "BEGIN IMMEDIATE;\n"
        f"{migration.sql}\n"
        f"PRAGMA user_version = {migration.version};\n"
        "COMMIT;"
    )


MIGRATIONS = (
    Migration(version=1, sql=_CREATE_CORE_SCHEMA),
    Migration(version=2, sql=_CREATE_ARTIFACT_REFERENCES),
    Migration(version=3, sql=_WIDEN_ARTIFACT_REFERENCES_PRESENCE),
)


def migrate(conn: Connection) -> None:
    """Apply pending SQLite migrations."""

    current_version = conn.execute("PRAGMA user_version").fetchone()[0]
    if current_version > SCHEMA_VERSION:
        raise RuntimeError(
            f"database schema version {current_version} is newer than supported "
            f"version {SCHEMA_VERSION}"
        )

    for migration in MIGRATIONS:
        if current_version >= migration.version:
            continue
        # The script manages its own transaction (see atomic_migration_script);
        # executescript() alone is NOT atomic across statements.
        conn.executescript(atomic_migration_script(migration))
        current_version = migration.version


def initialize(conn: Connection) -> Connection:
    """Initialize a connection and return it for fluent setup."""

    migrate(conn)
    return conn
