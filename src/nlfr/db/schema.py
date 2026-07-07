"""SQLite schema and migration helpers for the NLFR data spine."""

from __future__ import annotations

from dataclasses import dataclass
from sqlite3 import Connection

SCHEMA_VERSION = 2

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

_PRESENCE_CHECK = (
    "presence IS NULL OR presence IN "
    "('local_verified','local_mismatch','missing','unverified_remote_reference')"
)

_CREATE_ARTIFACT_REFERENCES = f"""
CREATE TABLE IF NOT EXISTS artifact_references (
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
    presence TEXT CHECK ({_PRESENCE_CHECK}),
    verification_note TEXT,
{_COMMON_COLUMNS},
    UNIQUE(run_id, reference_key)
);

CREATE INDEX IF NOT EXISTS idx_artifact_references_run_id ON artifact_references(run_id);
"""


@dataclass(frozen=True)
class Migration:
    version: int
    sql: str


MIGRATIONS = (
    Migration(version=1, sql=_CREATE_CORE_SCHEMA),
    Migration(version=2, sql=_CREATE_ARTIFACT_REFERENCES),
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
        with conn:
            conn.executescript(migration.sql)
            conn.execute(f"PRAGMA user_version = {migration.version}")
        current_version = migration.version


def initialize(conn: Connection) -> Connection:
    """Initialize a connection and return it for fluent setup."""

    migrate(conn)
    return conn
