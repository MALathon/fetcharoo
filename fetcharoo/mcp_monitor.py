"""
MCP source monitoring for fetcharoo.

Snapshots the output of MCP server tools over time and diffs against
previous snapshots to detect changes. Avoids wasteful repeated querying
by storing full snapshots and only surfacing what's new/changed/removed.

Works with any MCP server — clinical trials, document repositories,
data feeds, etc.

Usage (CLI):
    fetcharoo monitor snapshot --server "python clinical_trials_server.py" \\
        --tool search_studies --params '{"query.cond": "diabetes"}' \\
        --record-id-field "protocolSection.identificationModule.nctId"

    fetcharoo monitor diff --source "search_studies:diabetes"

Usage (Python API):
    from fetcharoo.mcp_monitor import SnapshotStore, snapshot_mcp_tool

    store = SnapshotStore()
    result = await snapshot_mcp_tool(
        store=store,
        server_command=["python", "clinical_trials_server.py"],
        tool_name="search_studies",
        tool_params={"query.cond": "diabetes"},
        record_id_field="protocolSection.identificationModule.nctId",
    )
    print(f"New: {len(result.new)}, Changed: {len(result.changed)}, Removed: {len(result.removed)}")
"""

import hashlib
import json
import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger('fetcharoo')


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_json(data: Any) -> str:
    """Deterministic hash of a JSON-serializable value."""
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()


def _extract_nested(obj: Any, dotted_key: str) -> Any:
    """
    Extract a value from a nested dict/list using dot notation.

    Examples:
        _extract_nested({"a": {"b": 1}}, "a.b") -> 1
        _extract_nested({"items": [{"id": 1}]}, "items.0.id") -> 1
    """
    parts = dotted_key.split('.')
    current = obj
    for part in parts:
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, (list, tuple)):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return current


@dataclass
class SnapshotRecord:
    """A single record within a snapshot."""
    record_id: str
    content_hash: str
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SnapshotDiff:
    """Result of comparing current snapshot against previous."""
    source_key: str
    timestamp: str = ''
    new: List[SnapshotRecord] = field(default_factory=list)
    changed: List[SnapshotRecord] = field(default_factory=list)
    removed: List[SnapshotRecord] = field(default_factory=list)
    unchanged: List[SnapshotRecord] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.new or self.changed or self.removed)

    @property
    def summary(self) -> str:
        return (
            f"new={len(self.new)} changed={len(self.changed)} "
            f"removed={len(self.removed)} unchanged={len(self.unchanged)}"
        )


class SnapshotStore:
    """
    SQLite-backed store for MCP tool output snapshots.

    Each "source" is identified by a key (e.g., "search_studies:diabetes").
    Each source has records identified by a record_id extracted from the data.
    Records are tracked across snapshots via content hashing.
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            catalog_dir = os.path.join(os.path.expanduser('~'), '.fetcharoo')
            os.makedirs(catalog_dir, exist_ok=True)
            db_path = os.path.join(catalog_dir, 'catalog.db')

        self.db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_key TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    record_count INTEGER DEFAULT 0,
                    new_count INTEGER DEFAULT 0,
                    changed_count INTEGER DEFAULT 0,
                    removed_count INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS snapshot_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_key TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    data TEXT NOT NULL DEFAULT '{}',
                    first_seen TEXT,
                    last_seen TEXT,
                    last_changed TEXT,
                    status TEXT DEFAULT 'active'
                );

                CREATE INDEX IF NOT EXISTS idx_snap_records_source
                    ON snapshot_records(source_key);
                CREATE INDEX IF NOT EXISTS idx_snap_records_source_record
                    ON snapshot_records(source_key, record_id);
                CREATE INDEX IF NOT EXISTS idx_snap_records_status
                    ON snapshot_records(status);
                CREATE INDEX IF NOT EXISTS idx_snapshots_source
                    ON snapshots(source_key);
            """)

    def take_snapshot(
        self,
        source_key: str,
        records: List[Dict[str, Any]],
        record_id_field: str,
    ) -> SnapshotDiff:
        """
        Store a new snapshot and diff against the previous one.

        Args:
            source_key: Identifier for this data source (e.g., "search_studies:diabetes").
            records: List of dicts — the raw MCP tool output records.
            record_id_field: Dot-notation path to the unique ID within each record
                            (e.g., "protocolSection.identificationModule.nctId").

        Returns:
            SnapshotDiff showing what changed.
        """
        now = _now_iso()

        # Build current records with IDs and hashes
        current: Dict[str, SnapshotRecord] = {}
        for item in records:
            rid = _extract_nested(item, record_id_field)
            if rid is None:
                # Try using the whole item hash as ID
                rid = _hash_json(item)[:16]
            rid = str(rid)
            current[rid] = SnapshotRecord(
                record_id=rid,
                content_hash=_hash_json(item),
                data=item,
            )

        # Load previous records for this source
        previous = self._get_active_records(source_key)

        # Compute diff
        diff = SnapshotDiff(source_key=source_key, timestamp=now)

        for rid, rec in current.items():
            if rid not in previous:
                diff.new.append(rec)
                self._upsert_record(source_key, rec, now, is_new=True)
            elif previous[rid]['content_hash'] != rec.content_hash:
                diff.changed.append(rec)
                self._upsert_record(source_key, rec, now, is_new=False, changed=True)
            else:
                diff.unchanged.append(rec)
                self._touch_record(source_key, rid, now)

        for rid, row in previous.items():
            if rid not in current:
                removed_rec = SnapshotRecord(
                    record_id=rid,
                    content_hash=row['content_hash'],
                    data=json.loads(row['data']),
                )
                diff.removed.append(removed_rec)
                self._mark_removed(source_key, rid, now)

        # Record the snapshot
        with self._conn:
            self._conn.execute(
                """INSERT INTO snapshots
                   (source_key, timestamp, record_count, new_count, changed_count, removed_count)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (source_key, now, len(current), len(diff.new),
                 len(diff.changed), len(diff.removed))
            )

        return diff

    def get_current_records(self, source_key: str) -> List[Dict[str, Any]]:
        """Get all active records for a source."""
        rows = self._conn.execute(
            "SELECT * FROM snapshot_records WHERE source_key = ? AND status = 'active' ORDER BY record_id",
            (source_key,)
        ).fetchall()
        return [json.loads(r['data']) for r in rows]

    def get_record(self, source_key: str, record_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific record by source and ID."""
        row = self._conn.execute(
            "SELECT * FROM snapshot_records WHERE source_key = ? AND record_id = ?",
            (source_key, record_id)
        ).fetchone()
        if row is None:
            return None
        return {
            'record_id': row['record_id'],
            'content_hash': row['content_hash'],
            'data': json.loads(row['data']),
            'first_seen': row['first_seen'],
            'last_seen': row['last_seen'],
            'last_changed': row['last_changed'],
            'status': row['status'],
        }

    def get_snapshot_history(self, source_key: Optional[str] = None, limit: int = 20) -> List[Dict]:
        """Get snapshot run history."""
        if source_key:
            rows = self._conn.execute(
                "SELECT * FROM snapshots WHERE source_key = ? ORDER BY timestamp DESC LIMIT ?",
                (source_key, limit)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM snapshots ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def list_sources(self) -> List[Dict[str, Any]]:
        """List all tracked sources with their record counts."""
        rows = self._conn.execute("""
            SELECT source_key, COUNT(*) as record_count,
                   SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active_count,
                   MAX(last_seen) as last_updated
            FROM snapshot_records
            GROUP BY source_key
            ORDER BY source_key
        """).fetchall()
        return [dict(r) for r in rows]

    def search_records(self, query: str, source_key: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search across snapshot records by data content."""
        pattern = f"%{query}%"
        if source_key:
            rows = self._conn.execute(
                "SELECT * FROM snapshot_records WHERE source_key = ? AND data LIKE ? AND status = 'active'",
                (source_key, pattern)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM snapshot_records WHERE data LIKE ? AND status = 'active'",
                (pattern,)
            ).fetchall()
        return [
            {
                'source_key': r['source_key'],
                'record_id': r['record_id'],
                'data': json.loads(r['data']),
                'first_seen': r['first_seen'],
                'last_seen': r['last_seen'],
            }
            for r in rows
        ]

    def export_json(self, source_key: Optional[str] = None) -> str:
        """Export snapshot records as JSON."""
        if source_key:
            rows = self._conn.execute(
                "SELECT * FROM snapshot_records WHERE source_key = ? ORDER BY record_id",
                (source_key,)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM snapshot_records ORDER BY source_key, record_id"
            ).fetchall()
        data = [
            {
                'source_key': r['source_key'],
                'record_id': r['record_id'],
                'content_hash': r['content_hash'],
                'data': json.loads(r['data']),
                'first_seen': r['first_seen'],
                'last_seen': r['last_seen'],
                'last_changed': r['last_changed'],
                'status': r['status'],
            }
            for r in rows
        ]
        return json.dumps(data, indent=2)

    def close(self) -> None:
        self._conn.close()

    # --- Internal helpers ---

    def _get_active_records(self, source_key: str) -> Dict[str, sqlite3.Row]:
        rows = self._conn.execute(
            "SELECT * FROM snapshot_records WHERE source_key = ? AND status = 'active'",
            (source_key,)
        ).fetchall()
        return {r['record_id']: r for r in rows}

    def _upsert_record(
        self, source_key: str, rec: SnapshotRecord, now: str,
        is_new: bool, changed: bool = False
    ) -> None:
        with self._conn:
            if is_new:
                self._conn.execute(
                    """INSERT OR REPLACE INTO snapshot_records
                       (source_key, record_id, content_hash, data, first_seen, last_seen, last_changed, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 'active')""",
                    (source_key, rec.record_id, rec.content_hash,
                     json.dumps(rec.data, default=str), now, now, now)
                )
            else:
                self._conn.execute(
                    """UPDATE snapshot_records SET content_hash=?, data=?, last_seen=?,
                       last_changed=?, status='active'
                       WHERE source_key=? AND record_id=?""",
                    (rec.content_hash, json.dumps(rec.data, default=str),
                     now, now if changed else now,
                     source_key, rec.record_id)
                )

    def _touch_record(self, source_key: str, record_id: str, now: str) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE snapshot_records SET last_seen=? WHERE source_key=? AND record_id=?",
                (now, source_key, record_id)
            )

    def _mark_removed(self, source_key: str, record_id: str, now: str) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE snapshot_records SET status='removed', last_seen=? WHERE source_key=? AND record_id=?",
                (now, source_key, record_id)
            )


# --- MCP Tool Snapshotting ---

async def snapshot_mcp_tool(
    store: SnapshotStore,
    server_command: Union[str, List[str]],
    tool_name: str,
    tool_params: Optional[Dict[str, Any]] = None,
    record_id_field: str = "id",
    source_key: Optional[str] = None,
    results_field: Optional[str] = None,
) -> SnapshotDiff:
    """
    Call an MCP tool, snapshot the results, and diff against previous snapshot.

    Args:
        store: SnapshotStore for persistence.
        server_command: Command to start the MCP server (e.g., ["python", "server.py"]).
        tool_name: Name of the MCP tool to call.
        tool_params: Parameters to pass to the tool.
        record_id_field: Dot-notation path to the unique ID in each record.
        source_key: Identifier for this source. Defaults to "{tool_name}:{params_hash}".
        results_field: Dot-notation path to the array of records in the tool output.
                      If None, assumes the output is already a list or tries common fields.

    Returns:
        SnapshotDiff with new/changed/removed/unchanged records.
    """
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError:
        raise ImportError(
            "MCP client support requires the 'mcp' package. "
            "Install with: pip install mcp"
        )

    if tool_params is None:
        tool_params = {}

    if source_key is None:
        params_hash = _hash_json(tool_params)[:8]
        source_key = f"{tool_name}:{params_hash}"

    if isinstance(server_command, str):
        server_command = server_command.split()

    server_params = StdioServerParameters(
        command=server_command[0],
        args=server_command[1:] if len(server_command) > 1 else [],
    )

    # Connect to MCP server and call the tool
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            result = await session.call_tool(tool_name, arguments=tool_params)

            # Parse the result
            raw_output = _parse_mcp_result(result, results_field)

    return store.take_snapshot(source_key, raw_output, record_id_field)


def snapshot_data(
    store: SnapshotStore,
    source_key: str,
    records: List[Dict[str, Any]],
    record_id_field: str = "id",
) -> SnapshotDiff:
    """
    Snapshot arbitrary data (not from MCP) and diff against previous.

    This is the synchronous, non-MCP entry point. Useful for:
    - Data from REST APIs you've already fetched
    - Data from files or databases
    - Testing

    Args:
        store: SnapshotStore for persistence.
        source_key: Identifier for this data source.
        records: List of dicts to snapshot.
        record_id_field: Dot-notation path to unique ID in each record.

    Returns:
        SnapshotDiff with new/changed/removed/unchanged records.
    """
    return store.take_snapshot(source_key, records, record_id_field)


def _parse_mcp_result(result: Any, results_field: Optional[str] = None) -> List[Dict]:
    """Parse MCP tool result into a list of records."""
    # MCP results have a .content list with TextContent items
    raw_text = ""
    if hasattr(result, 'content'):
        for item in result.content:
            if hasattr(item, 'text'):
                raw_text += item.text

    if not raw_text:
        return []

    # Try parsing as JSON
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        # Not JSON — treat each line as a record
        return [{"text": line} for line in raw_text.strip().split('\n') if line.strip()]

    # If a results_field is specified, extract it
    if results_field:
        parsed = _extract_nested(parsed, results_field)
        if parsed is None:
            return []

    # If it's already a list, return it
    if isinstance(parsed, list):
        return parsed

    # If it's a dict, look for common array fields
    if isinstance(parsed, dict):
        for key in ('results', 'studies', 'data', 'items', 'records', 'trials'):
            if key in parsed and isinstance(parsed[key], list):
                return parsed[key]
        # Single record
        return [parsed]

    return []
