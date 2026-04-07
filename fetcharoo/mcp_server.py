"""
MCP (Model Context Protocol) server for fetcharoo.

Exposes fetcharoo's stateful capabilities as MCP tools, enabling AI agents
to discover, download, and track PDF documents persistently.

Usage:
    fetcharoo mcp serve
    # or directly:
    python -m fetcharoo.mcp_server
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


def create_server():
    """
    Create and configure the fetcharoo MCP server.

    Returns:
        A configured FastMCP server instance.

    Raises:
        ImportError: If the mcp package is not installed.
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        raise ImportError(
            "MCP support requires the 'mcp' package. "
            "Install it with: pip install 'fetcharoo[mcp]' or pip install mcp"
        )

    from fetcharoo.catalog import DocumentCatalog, DiffResult
    from fetcharoo.fetcharoo import find_pdfs_from_webpage, download_pdfs_from_webpage
    from fetcharoo.filtering import FilterConfig
    from fetcharoo.watcher import diff_once

    mcp = FastMCP(
        "fetcharoo",
        description="PDF document discovery, download, and tracking from websites",
    )

    # Shared catalog instance
    _catalog = DocumentCatalog()

    @mcp.tool()
    def discover_pdfs(
        url: str,
        recursion_depth: int = 0,
        include_patterns: Optional[list] = None,
        exclude_patterns: Optional[list] = None,
    ) -> str:
        """
        Discover all PDF documents available on a webpage.

        Crawls the given URL (optionally following links to the specified depth)
        and returns a structured list of all PDF URLs found.

        Args:
            url: The webpage URL to search for PDFs.
            recursion_depth: How many levels of links to follow (0-5).
            include_patterns: Filename patterns to include (e.g., ['report*.pdf']).
            exclude_patterns: Filename patterns to exclude (e.g., ['*draft*']).
        """
        pdf_urls = find_pdfs_from_webpage(
            url,
            recursion_depth=min(recursion_depth, 5),
        )

        # Apply filtering if patterns provided
        if include_patterns or exclude_patterns:
            from fetcharoo.filtering import should_download_pdf
            config = FilterConfig(
                filename_include=include_patterns or [],
                filename_exclude=exclude_patterns or [],
            )
            pdf_urls = [u for u in pdf_urls if should_download_pdf(u, filter_config=config)]

        # Record discoveries in catalog
        for pdf_url in pdf_urls:
            _catalog.record_discovery(pdf_url, source_page=url)

        return json.dumps({
            "source_url": url,
            "count": len(pdf_urls),
            "pdfs": pdf_urls,
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
        Download PDF documents from a webpage with fetcharoo's full reliability
        (retry logic, rate limiting, deduplication, security hardening).

        Args:
            url: The webpage URL to download PDFs from.
            output_dir: Directory to save downloaded PDFs.
            recursion_depth: How many levels of links to follow (0-5).
            merge: If True, merge all PDFs into a single file.
            output_name: Custom filename for merged output.
        """
        result = download_pdfs_from_webpage(
            url,
            recursion_depth=min(recursion_depth, 5),
            mode='merge' if merge else 'separate',
            write_dir=output_dir,
            output_name=output_name,
        )

        return json.dumps({
            "success": result.success,
            "downloaded_count": result.downloaded_count,
            "filtered_count": result.filtered_count,
            "failed_count": result.failed_count,
            "files_created": result.files_created,
            "errors": result.errors,
        }, indent=2)

    @mcp.tool()
    def catalog_query(
        source_url: Optional[str] = None,
    ) -> str:
        """
        Query the persistent document catalog.

        Shows all documents fetcharoo has ever seen, with metadata including
        when they were first/last seen, content hashes, and file sizes.
        This is persistent memory across sessions.

        Args:
            source_url: If provided, only show documents from this source page.
        """
        docs = _catalog.get_active_documents(source_page=source_url)
        return json.dumps({
            "total_documents": len(docs),
            "documents": [
                {
                    "url": d.url,
                    "filename": d.filename,
                    "size_bytes": d.size_bytes,
                    "first_seen": d.first_seen,
                    "last_seen": d.last_seen,
                    "last_changed": d.last_changed,
                    "status": d.status,
                    "metadata": d.metadata,
                }
                for d in docs
            ],
        }, indent=2)

    @mcp.tool()
    def catalog_diff(
        url: str,
        recursion_depth: int = 0,
    ) -> str:
        """
        Check what's changed since the last time fetcharoo looked at a URL.

        Compares the current state of PDFs on a webpage against what's stored
        in the catalog. Reports new, removed, and unchanged documents.

        Args:
            url: The webpage URL to check for changes.
            recursion_depth: How many levels of links to follow (0-5).
        """
        current_urls = find_pdfs_from_webpage(
            url,
            recursion_depth=min(recursion_depth, 5),
        )

        diff = _catalog.diff(current_urls)

        # Update catalog
        for doc in diff.new:
            _catalog.record_discovery(doc.url, source_page=url)
        for doc in diff.removed:
            _catalog.mark_removed(doc.url)
        _catalog.record_run(url, diff)

        return json.dumps({
            "source_url": url,
            "summary": {
                "new": len(diff.new),
                "changed": len(diff.changed),
                "removed": len(diff.removed),
                "unchanged": len(diff.unchanged),
            },
            "new_documents": [d.url for d in diff.new],
            "removed_documents": [d.url for d in diff.removed],
            "unchanged_documents": [d.url for d in diff.unchanged],
        }, indent=2)

    @mcp.tool()
    def catalog_search(
        query: str,
    ) -> str:
        """
        Search across all tracked documents by URL or filename substring.

        Args:
            query: Search string to match against document URLs and filenames.
        """
        docs = _catalog.search(query)
        return json.dumps({
            "query": query,
            "results_count": len(docs),
            "results": [
                {
                    "url": d.url,
                    "filename": d.filename,
                    "status": d.status,
                    "first_seen": d.first_seen,
                    "last_seen": d.last_seen,
                }
                for d in docs
            ],
        }, indent=2)

    @mcp.tool()
    def get_document_metadata(
        url: str,
    ) -> str:
        """
        Get detailed information about a specific tracked document.

        Args:
            url: The URL of the document to look up.
        """
        doc = _catalog.get_document(url)
        if doc is None:
            return json.dumps({"error": f"Document not found: {url}"})

        return json.dumps({
            "url": doc.url,
            "filename": doc.filename,
            "content_hash": doc.content_hash,
            "size_bytes": doc.size_bytes,
            "first_seen": doc.first_seen,
            "last_seen": doc.last_seen,
            "last_changed": doc.last_changed,
            "status": doc.status,
            "source_page": doc.source_page,
            "metadata": doc.metadata,
        }, indent=2)

    @mcp.tool()
    def find_duplicate_documents() -> str:
        """
        Find documents that have identical content but different URLs.

        Uses content hashing to detect when the same PDF exists at multiple URLs.
        """
        duplicates = _catalog.find_duplicates()
        result = {}
        for hash_val, docs in duplicates.items():
            result[hash_val] = [d.url for d in docs]

        return json.dumps({
            "duplicate_groups": len(result),
            "duplicates": result,
        }, indent=2)

    # --- Snapshot monitoring tools ---

    from fetcharoo.mcp_monitor import SnapshotStore, snapshot_data

    _snapshot_store = SnapshotStore()

    @mcp.tool()
    def snapshot_monitor(
        source_key: str,
        records: list,
        record_id_field: str = "id",
    ) -> str:
        """
        Snapshot a list of records and diff against the previous snapshot.

        Use this to monitor ANY data source for changes over time — clinical trials,
        document listings, API results, etc. Pass the data you've already fetched,
        and fetcharoo will tell you what's new, changed, or removed since last time.

        Args:
            source_key: A name for this data source (e.g., "diabetes-trials-recruiting").
            records: List of record dicts to snapshot.
            record_id_field: Dot-notation path to the unique ID in each record
                           (e.g., "protocolSection.identificationModule.nctId" for clinical trials,
                            or "id" for simpler records).
        """
        diff = snapshot_data(
            store=_snapshot_store,
            source_key=source_key,
            records=records,
            record_id_field=record_id_field,
        )
        return json.dumps({
            "source_key": diff.source_key,
            "has_changes": diff.has_changes,
            "summary": {
                "new": len(diff.new),
                "changed": len(diff.changed),
                "removed": len(diff.removed),
                "unchanged": len(diff.unchanged),
            },
            "new_records": [{"id": r.record_id, "data": r.data} for r in diff.new],
            "changed_records": [{"id": r.record_id, "data": r.data} for r in diff.changed],
            "removed_records": [{"id": r.record_id} for r in diff.removed],
        }, indent=2)

    @mcp.tool()
    def snapshot_query(
        source_key: str,
    ) -> str:
        """
        Get all current records for a monitored data source.

        Returns the latest snapshot of all active records.

        Args:
            source_key: The data source name (e.g., "diabetes-trials-recruiting").
        """
        records = _snapshot_store.get_current_records(source_key)
        return json.dumps({
            "source_key": source_key,
            "record_count": len(records),
            "records": records,
        }, indent=2)

    @mcp.tool()
    def snapshot_history(
        source_key: Optional[str] = None,
    ) -> str:
        """
        View the history of snapshot runs for a data source.

        Shows when each snapshot was taken and what changed.

        Args:
            source_key: Filter by source name. If None, shows all sources.
        """
        history = _snapshot_store.get_snapshot_history(source_key)
        return json.dumps({
            "runs": history,
        }, indent=2)

    @mcp.tool()
    def snapshot_sources() -> str:
        """
        List all data sources being monitored via snapshots.

        Shows each source with its record count and last update time.
        """
        sources = _snapshot_store.list_sources()
        return json.dumps({
            "sources": sources,
        }, indent=2)

    @mcp.tool()
    def snapshot_search(
        query: str,
        source_key: Optional[str] = None,
    ) -> str:
        """
        Search across all snapshot records by content.

        Args:
            query: Search string to match against record data.
            source_key: Optionally limit search to a specific source.
        """
        results = _snapshot_store.search_records(query, source_key)
        return json.dumps({
            "query": query,
            "results_count": len(results),
            "results": results,
        }, indent=2)

    return mcp


def main():
    """Run the fetcharoo MCP server."""
    if not _check_mcp_available():
        print(
            "Error: MCP support requires the 'mcp' package.\n"
            "Install it with: pip install 'fetcharoo[mcp]' or pip install mcp",
            file=sys.stderr,
        )
        sys.exit(1)

    server = create_server()
    server.run()


if __name__ == '__main__':
    main()
