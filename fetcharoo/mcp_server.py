"""
MCP server for fetcharoo.

A single MCP server that provides:
  1. PDF discovery, download, and tracking tools (always available)
  2. Snapshot monitoring for any data source (always available)
  3. Caching proxy for an upstream MCP server (when --upstream is provided)

Usage:
    # Standalone — PDF tools + snapshot monitoring
    fetcharoo mcp serve

    # With upstream proxy — all of the above + cached proxy to another MCP server
    fetcharoo mcp serve --upstream "npx trial-guide" --ttl 3600
"""

import json
import logging
import os
import sys
from typing import Optional

logger = logging.getLogger('fetcharoo')


def _check_mcp_available():
    """Check if the MCP/FastMCP library is installed."""
    try:
        from mcp.server.fastmcp import FastMCP
        return True
    except ImportError:
        return False


def create_server(
    upstream_command: Optional[str] = None,
    ttl: float = 3600,
    cache_db_path: Optional[str] = None,
):
    """
    Create the unified fetcharoo MCP server.

    Args:
        upstream_command: If provided, also proxy this upstream MCP server with caching.
        ttl: Cache TTL in seconds for proxied calls (default: 1 hour).
        cache_db_path: Path to cache/snapshot database.

    Returns:
        A configured FastMCP server instance.
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        raise ImportError(
            "MCP support requires the 'mcp' package. "
            "Install it with: pip install 'fetcharoo[mcp]' or pip install mcp"
        )

    from fetcharoo.catalog import DocumentCatalog
    from fetcharoo.fetcharoo import find_pdfs_from_webpage, download_pdfs_from_webpage
    from fetcharoo.filtering import FilterConfig
    from fetcharoo.mcp_monitor import SnapshotStore, snapshot_data
    from fetcharoo.mcp_proxy import ToolCache

    desc = "PDF discovery, document tracking, and snapshot monitoring"
    if upstream_command:
        desc += f" | caching proxy for: {upstream_command}"

    mcp = FastMCP("fetcharoo", description=desc)

    _catalog = DocumentCatalog()
    _snapshot_store = SnapshotStore()
    _tool_cache = ToolCache(db_path=cache_db_path) if upstream_command else None

    # ===== PDF tools (always available) =====

    @mcp.tool()
    def discover_pdfs(
        url: str,
        recursion_depth: int = 0,
        include_patterns: Optional[list] = None,
        exclude_patterns: Optional[list] = None,
    ) -> str:
        """
        Discover all PDF documents available on a webpage.

        Args:
            url: The webpage URL to search for PDFs.
            recursion_depth: How many levels of links to follow (0-5).
            include_patterns: Filename patterns to include (e.g., ['report*.pdf']).
            exclude_patterns: Filename patterns to exclude (e.g., ['*draft*']).
        """
        pdf_urls = find_pdfs_from_webpage(
            url, recursion_depth=min(recursion_depth, 5),
        )
        if include_patterns or exclude_patterns:
            from fetcharoo.filtering import should_download_pdf
            config = FilterConfig(
                filename_include=include_patterns or [],
                filename_exclude=exclude_patterns or [],
            )
            pdf_urls = [u for u in pdf_urls if should_download_pdf(u, filter_config=config)]

        for pdf_url in pdf_urls:
            _catalog.record_discovery(pdf_url, source_page=url)

        return json.dumps({
            "source_url": url, "count": len(pdf_urls), "pdfs": pdf_urls,
        }, indent=2)

    @mcp.tool()
    def download_pdfs(
        url: str,
        output_dir: str = "output",
        recursion_depth: int = 0,
        merge: bool = False,
        output_name: Optional[str] = None,
    ) -> str:
        """
        Download PDF documents from a webpage with full reliability.

        Args:
            url: The webpage URL to download PDFs from.
            output_dir: Directory to save downloaded PDFs.
            recursion_depth: How many levels of links to follow (0-5).
            merge: If True, merge all PDFs into a single file.
            output_name: Custom filename for merged output.
        """
        result = download_pdfs_from_webpage(
            url, recursion_depth=min(recursion_depth, 5),
            mode='merge' if merge else 'separate',
            write_dir=output_dir, output_name=output_name,
        )
        return json.dumps({
            "success": result.success,
            "downloaded_count": result.downloaded_count,
            "filtered_count": result.filtered_count,
            "failed_count": result.failed_count,
            "files_created": result.files_created,
            "errors": result.errors,
        }, indent=2)

    # ===== Catalog tools (always available) =====

    @mcp.tool()
    def catalog_query(source_url: Optional[str] = None) -> str:
        """Query the persistent document catalog. Shows all tracked documents."""
        docs = _catalog.get_active_documents(source_page=source_url)
        return json.dumps({
            "total_documents": len(docs),
            "documents": [
                {"url": d.url, "filename": d.filename, "size_bytes": d.size_bytes,
                 "first_seen": d.first_seen, "last_seen": d.last_seen,
                 "status": d.status, "metadata": d.metadata}
                for d in docs
            ],
        }, indent=2)

    @mcp.tool()
    def catalog_diff(url: str, recursion_depth: int = 0) -> str:
        """Check what PDFs have changed since last check on a URL."""
        current_urls = find_pdfs_from_webpage(url, recursion_depth=min(recursion_depth, 5))
        diff = _catalog.diff(current_urls)
        for doc in diff.new:
            _catalog.record_discovery(doc.url, source_page=url)
        for doc in diff.removed:
            _catalog.mark_removed(doc.url)
        _catalog.record_run(url, diff)
        return json.dumps({
            "source_url": url,
            "summary": {"new": len(diff.new), "changed": len(diff.changed),
                        "removed": len(diff.removed), "unchanged": len(diff.unchanged)},
            "new_documents": [d.url for d in diff.new],
            "removed_documents": [d.url for d in diff.removed],
        }, indent=2)

    @mcp.tool()
    def catalog_search(query: str) -> str:
        """Search tracked documents by URL or filename."""
        docs = _catalog.search(query)
        return json.dumps({
            "query": query, "results_count": len(docs),
            "results": [{"url": d.url, "filename": d.filename, "status": d.status,
                         "first_seen": d.first_seen, "last_seen": d.last_seen}
                        for d in docs],
        }, indent=2)

    @mcp.tool()
    def get_document_metadata(url: str) -> str:
        """Get detailed info about a tracked document."""
        doc = _catalog.get_document(url)
        if doc is None:
            return json.dumps({"error": f"Document not found: {url}"})
        return json.dumps({
            "url": doc.url, "filename": doc.filename,
            "content_hash": doc.content_hash, "size_bytes": doc.size_bytes,
            "first_seen": doc.first_seen, "last_seen": doc.last_seen,
            "last_changed": doc.last_changed, "status": doc.status,
            "source_page": doc.source_page, "metadata": doc.metadata,
        }, indent=2)

    @mcp.tool()
    def find_duplicate_documents() -> str:
        """Find documents with identical content at different URLs."""
        duplicates = _catalog.find_duplicates()
        result = {h: [d.url for d in docs] for h, docs in duplicates.items()}
        return json.dumps({"duplicate_groups": len(result), "duplicates": result}, indent=2)

    # ===== Snapshot monitoring tools (always available) =====

    @mcp.tool()
    def snapshot(
        source_key: str,
        records: list,
        record_id_field: str = "id",
    ) -> str:
        """
        Snapshot a list of records and diff against the previous snapshot.

        Use this to monitor ANY data source for changes over time.
        Pass data you've already fetched from any tool or API, and get back
        what's new, changed, or removed since last time.

        Args:
            source_key: Name for this data source (e.g., "diabetes-trials").
            records: List of record dicts to snapshot.
            record_id_field: Dot-notation path to the unique ID in each record.
        """
        diff = snapshot_data(
            store=_snapshot_store, source_key=source_key,
            records=records, record_id_field=record_id_field,
        )
        return json.dumps({
            "source_key": diff.source_key, "has_changes": diff.has_changes,
            "summary": {"new": len(diff.new), "changed": len(diff.changed),
                        "removed": len(diff.removed), "unchanged": len(diff.unchanged)},
            "new_records": [{"id": r.record_id, "data": r.data} for r in diff.new],
            "changed_records": [{"id": r.record_id, "data": r.data} for r in diff.changed],
            "removed_records": [{"id": r.record_id} for r in diff.removed],
        }, indent=2)

    @mcp.tool()
    def snapshot_query(source_key: str) -> str:
        """Get all current records for a monitored data source."""
        records = _snapshot_store.get_current_records(source_key)
        return json.dumps({
            "source_key": source_key, "record_count": len(records), "records": records,
        }, indent=2)

    @mcp.tool()
    def snapshot_sources() -> str:
        """List all data sources being monitored."""
        sources = _snapshot_store.list_sources()
        return json.dumps({"sources": sources}, indent=2)

    @mcp.tool()
    def snapshot_search(query: str, source_key: Optional[str] = None) -> str:
        """Search across all snapshot records by content."""
        results = _snapshot_store.search_records(query, source_key)
        return json.dumps({
            "query": query, "results_count": len(results), "results": results,
        }, indent=2)

    # ===== Upstream proxy tools (only when --upstream is provided) =====

    if upstream_command and _tool_cache:
        import asyncio
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        parts = upstream_command.split()
        upstream_params = StdioServerParameters(
            command=parts[0],
            args=parts[1:] if len(parts) > 1 else [],
        )

        async def _call_upstream(tool_name: str, arguments: dict) -> str:
            async with stdio_client(upstream_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments=arguments)
                    text_parts = []
                    if hasattr(result, 'content'):
                        for item in result.content:
                            if hasattr(item, 'text'):
                                text_parts.append(item.text)
                    return "\n".join(text_parts)

        def _call_upstream_sync(tool_name: str, arguments: dict) -> str:
            return asyncio.run(_call_upstream(tool_name, arguments))

        @mcp.tool()
        def upstream_call(
            tool_name: str,
            arguments: Optional[dict] = None,
            bypass_cache: bool = False,
        ) -> str:
            """
            Call a tool on the upstream MCP server through the cache.

            First checks the cache. If the result is fresh (within TTL), returns
            the cached version. Otherwise calls upstream, caches, and returns.

            Args:
                tool_name: Name of the upstream tool to call.
                arguments: Arguments dict to pass to the tool.
                bypass_cache: If True, skip cache and always call upstream.
            """
            if arguments is None:
                arguments = {}

            from fetcharoo.mcp_proxy import _cache_key

            if not bypass_cache:
                cached = _tool_cache.get(tool_name, arguments, ttl=ttl)
                if cached is not None:
                    key = _cache_key(tool_name, arguments)
                    return json.dumps({
                        "_source": "cache", "_cache_key": key, "result": cached,
                    })

            result_text = _call_upstream_sync(tool_name, arguments)
            changed = _tool_cache.put(tool_name, arguments, result_text)
            key = _cache_key(tool_name, arguments)
            return json.dumps({
                "_source": "upstream", "_cache_key": key,
                "_changed_since_last": changed, "result": result_text,
            }, indent=2)

        @mcp.tool()
        def upstream_refresh(tool_name: str, arguments: Optional[dict] = None) -> str:
            """
            Force-refresh a cached upstream tool call (bypass TTL).

            Args:
                tool_name: The upstream tool to refresh.
                arguments: Arguments to pass.
            """
            if arguments is None:
                arguments = {}
            from fetcharoo.mcp_proxy import _cache_key
            result_text = _call_upstream_sync(tool_name, arguments)
            changed = _tool_cache.put(tool_name, arguments, result_text)
            key = _cache_key(tool_name, arguments)
            return json.dumps({
                "cache_key": key, "changed_since_last": changed, "result": result_text,
            }, indent=2)

        @mcp.tool()
        def cache_status() -> str:
            """Show all cached upstream tool calls and their freshness."""
            entries = _tool_cache.get_all_entries()
            return json.dumps({
                "upstream": upstream_command, "ttl_seconds": ttl,
                "cache_entries": len(entries), "entries": entries,
            }, indent=2)

        @mcp.tool()
        def cache_clear(tool_name: Optional[str] = None) -> str:
            """Clear the upstream cache. Optionally filter by tool name."""
            count = _tool_cache.invalidate(tool_name)
            return json.dumps({"cleared": count, "tool_name": tool_name or "all"})

    return mcp


def main(upstream: Optional[str] = None, ttl: float = 3600, cache_db: Optional[str] = None):
    """Run the fetcharoo MCP server."""
    if not _check_mcp_available():
        print(
            "Error: MCP support requires the 'mcp' package.\n"
            "Install it with: pip install 'fetcharoo[mcp]' or pip install mcp",
            file=sys.stderr,
        )
        sys.exit(1)

    server = create_server(upstream_command=upstream, ttl=ttl, cache_db_path=cache_db)
    server.run()


if __name__ == '__main__':
    main()
