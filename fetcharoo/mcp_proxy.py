"""
MCP caching proxy for fetcharoo.

Sits between an AI agent and any upstream MCP server. Intercepts tool calls,
caches results in SQLite, serves from cache when fresh, and provides automatic
diff/snapshot capabilities for every proxied tool.

Think of it as Redis for MCP servers.

Architecture:
    AI Agent <--MCP--> fetcharoo proxy <--MCP--> upstream server (e.g., trial-guide)

The proxy:
    1. Connects to the upstream MCP server on startup
    2. Discovers all its tools
    3. Re-exposes each tool with caching + diff wrappers
    4. Adds meta-tools: _cache_diff, _cache_query, _cache_sources, _cache_clear

Usage:
    # CLI
    fetcharoo proxy --server "npx trial-guide" --ttl 3600

    # This starts a new MCP server that proxies all tools from trial-guide
    # with 1-hour caching. Connect to it from Claude Desktop like any MCP server.

    # In Claude Desktop config:
    {
        "mcpServers": {
            "trial-guide-cached": {
                "command": "fetcharoo",
                "args": ["proxy", "--server", "npx trial-guide", "--ttl", "3600"]
            }
        }
    }
"""

import hashlib
import json
import logging
import os
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger('fetcharoo')


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_json(data: Any) -> str:
    serialized = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()


def _cache_key(tool_name: str, arguments: Dict[str, Any]) -> str:
    """Generate a deterministic cache key for a tool call."""
    args_hash = _hash_json(arguments)[:12]
    return f"{tool_name}:{args_hash}"


class ToolCache:
    """
    SQLite-backed cache for MCP tool call results.

    Stores tool call results with TTL-based freshness and content-hash-based
    change detection. Supports diffing current vs. cached results.
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            cache_dir = os.path.join(os.path.expanduser('~'), '.fetcharoo')
            os.makedirs(cache_dir, exist_ok=True)
            db_path = os.path.join(cache_dir, 'mcp_cache.db')

        self.db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS tool_cache (
                    cache_key TEXT PRIMARY KEY,
                    tool_name TEXT NOT NULL,
                    arguments TEXT NOT NULL DEFAULT '{}',
                    result_text TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    cached_at TEXT NOT NULL,
                    hit_count INTEGER DEFAULT 0,
                    previous_hash TEXT
                );

                CREATE TABLE IF NOT EXISTS cache_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cache_key TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    changed INTEGER DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_tool_cache_tool
                    ON tool_cache(tool_name);
                CREATE INDEX IF NOT EXISTS idx_cache_history_key
                    ON cache_history(cache_key);
            """)

    def get(self, tool_name: str, arguments: Dict[str, Any], ttl: float = 3600) -> Optional[str]:
        """
        Get a cached result if it exists and is fresh.

        Args:
            tool_name: Name of the MCP tool.
            arguments: Tool call arguments.
            ttl: Time-to-live in seconds. 0 = always stale.

        Returns:
            Cached result text, or None if cache miss or stale.
        """
        key = _cache_key(tool_name, arguments)
        row = self._conn.execute(
            "SELECT * FROM tool_cache WHERE cache_key = ?", (key,)
        ).fetchone()

        if row is None:
            return None

        if ttl <= 0:
            return None

        cached_at = datetime.fromisoformat(row['cached_at'])
        age = (datetime.now(timezone.utc) - cached_at).total_seconds()
        if age > ttl:
            return None

        # Cache hit — bump counter
        with self._conn:
            self._conn.execute(
                "UPDATE tool_cache SET hit_count = hit_count + 1 WHERE cache_key = ?",
                (key,)
            )

        return row['result_text']

    def put(self, tool_name: str, arguments: Dict[str, Any], result_text: str) -> bool:
        """
        Store a tool result in the cache.

        Args:
            tool_name: Name of the MCP tool.
            arguments: Tool call arguments.
            result_text: The tool's text result.

        Returns:
            True if the result is different from the previously cached value.
        """
        key = _cache_key(tool_name, arguments)
        new_hash = _hash_json(result_text)
        now = _now_iso()

        # Check if content changed
        old_row = self._conn.execute(
            "SELECT content_hash FROM tool_cache WHERE cache_key = ?", (key,)
        ).fetchone()
        old_hash = old_row['content_hash'] if old_row else None
        changed = old_hash is not None and old_hash != new_hash

        with self._conn:
            self._conn.execute(
                """INSERT OR REPLACE INTO tool_cache
                   (cache_key, tool_name, arguments, result_text, content_hash,
                    cached_at, hit_count, previous_hash)
                   VALUES (?, ?, ?, ?, ?, ?, 0, ?)""",
                (key, tool_name, json.dumps(arguments, default=str),
                 result_text, new_hash, now, old_hash)
            )
            self._conn.execute(
                """INSERT INTO cache_history
                   (cache_key, tool_name, content_hash, timestamp, changed)
                   VALUES (?, ?, ?, ?, ?)""",
                (key, tool_name, new_hash, now, 1 if changed else 0)
            )

        return changed

    def get_all_entries(self, tool_name: Optional[str] = None) -> List[Dict]:
        """List all cache entries, optionally filtered by tool name."""
        if tool_name:
            rows = self._conn.execute(
                "SELECT cache_key, tool_name, arguments, cached_at, hit_count, content_hash FROM tool_cache WHERE tool_name = ?",
                (tool_name,)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT cache_key, tool_name, arguments, cached_at, hit_count, content_hash FROM tool_cache"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_history(self, cache_key: Optional[str] = None, limit: int = 20) -> List[Dict]:
        """Get cache change history."""
        if cache_key:
            rows = self._conn.execute(
                "SELECT * FROM cache_history WHERE cache_key = ? ORDER BY timestamp DESC LIMIT ?",
                (cache_key, limit)
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM cache_history ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def invalidate(self, tool_name: Optional[str] = None) -> int:
        """
        Clear cache entries.

        Args:
            tool_name: If provided, only clear entries for this tool.
                      If None, clear everything.

        Returns:
            Number of entries removed.
        """
        if tool_name:
            cursor = self._conn.execute(
                "DELETE FROM tool_cache WHERE tool_name = ?", (tool_name,)
            )
        else:
            cursor = self._conn.execute("DELETE FROM tool_cache")
        self._conn.commit()
        return cursor.rowcount

    def close(self) -> None:
        self._conn.close()


def create_proxy_server(
    upstream_command: str,
    ttl: float = 3600,
    cache_db_path: Optional[str] = None,
):
    """
    Create an MCP proxy server that caches results from an upstream MCP server.

    Args:
        upstream_command: Shell command to start the upstream MCP server.
        ttl: Default cache TTL in seconds (0 = no caching, always forward).
        cache_db_path: Path to cache database.

    Returns:
        A configured FastMCP server instance.
    """
    try:
        from mcp.server.fastmcp import FastMCP
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError:
        raise ImportError(
            "MCP proxy requires the 'mcp' package. "
            "Install with: pip install mcp"
        )

    import asyncio

    cache = ToolCache(db_path=cache_db_path)

    parts = upstream_command.split()
    upstream_params = StdioServerParameters(
        command=parts[0],
        args=parts[1:] if len(parts) > 1 else [],
    )

    proxy = FastMCP(
        "fetcharoo-proxy",
        description=f"Caching proxy for: {upstream_command}",
    )

    # We'll store the upstream session info for tool discovery
    _upstream_tools: List[Dict] = []

    async def _call_upstream(tool_name: str, arguments: Dict[str, Any]) -> str:
        """Call a tool on the upstream MCP server."""
        async with stdio_client(upstream_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments=arguments)

                # Extract text from result
                text_parts = []
                if hasattr(result, 'content'):
                    for item in result.content:
                        if hasattr(item, 'text'):
                            text_parts.append(item.text)
                return "\n".join(text_parts)

    def _call_upstream_sync(tool_name: str, arguments: Dict[str, Any]) -> str:
        """Synchronous wrapper for calling upstream."""
        return asyncio.run(_call_upstream(tool_name, arguments))

    # --- Meta-tools (always available) ---

    @proxy.tool()
    def _cache_status() -> str:
        """
        Show all cached tool calls and their freshness.

        Returns cache entries with their age, hit count, and whether
        the result changed since the previous call.
        """
        entries = cache.get_all_entries()
        return json.dumps({
            "cache_entries": len(entries),
            "ttl_seconds": ttl,
            "entries": entries,
        }, indent=2)

    @proxy.tool()
    def _cache_history(cache_key: Optional[str] = None, limit: int = 20) -> str:
        """
        View change history for cached tool calls.

        Shows when each call was made and whether the result changed.

        Args:
            cache_key: Filter by specific cache key. None shows all.
            limit: Maximum entries to return.
        """
        history = cache.get_history(cache_key, limit)
        return json.dumps({
            "history": history,
        }, indent=2)

    @proxy.tool()
    def _cache_clear(tool_name: Optional[str] = None) -> str:
        """
        Clear the cache.

        Args:
            tool_name: Clear only entries for this tool. None clears everything.
        """
        count = cache.invalidate(tool_name)
        return json.dumps({
            "cleared": count,
            "tool_name": tool_name or "all",
        })

    @proxy.tool()
    def _cache_refresh(tool_name: str, arguments: Optional[dict] = None) -> str:
        """
        Force-refresh a cached tool call (bypass TTL, call upstream, cache new result).

        Args:
            tool_name: The upstream tool to call.
            arguments: Arguments to pass. Defaults to empty dict.
        """
        if arguments is None:
            arguments = {}

        result_text = _call_upstream_sync(tool_name, arguments)
        changed = cache.put(tool_name, arguments, result_text)

        key = _cache_key(tool_name, arguments)
        return json.dumps({
            "cache_key": key,
            "changed_since_last": changed,
            "result": result_text,
        }, indent=2)

    @proxy.tool()
    def _proxy_call(tool_name: str, arguments: Optional[dict] = None, bypass_cache: bool = False) -> str:
        """
        Call any tool on the upstream MCP server through the cache.

        This is the universal proxy tool. It checks the cache first (unless
        bypass_cache=True), calls the upstream server if needed, and caches
        the result.

        Args:
            tool_name: Name of the upstream tool to call.
            arguments: Arguments dict to pass to the tool.
            bypass_cache: If True, skip cache and always call upstream.
        """
        if arguments is None:
            arguments = {}

        # Check cache first
        if not bypass_cache:
            cached = cache.get(tool_name, arguments, ttl=ttl)
            if cached is not None:
                key = _cache_key(tool_name, arguments)
                return json.dumps({
                    "_source": "cache",
                    "_cache_key": key,
                    "result": cached,
                })

        # Cache miss or bypass — call upstream
        result_text = _call_upstream_sync(tool_name, arguments)
        changed = cache.put(tool_name, arguments, result_text)

        key = _cache_key(tool_name, arguments)
        return json.dumps({
            "_source": "upstream",
            "_cache_key": key,
            "_changed_since_last": changed,
            "result": result_text,
        }, indent=2)

    return proxy


def run_proxy(upstream_command: str, ttl: float = 3600, cache_db_path: Optional[str] = None):
    """Start the proxy server."""
    server = create_proxy_server(upstream_command, ttl, cache_db_path)
    server.run()
