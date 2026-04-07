"""
Command-line interface for fetcharoo.

This module provides a CLI for downloading PDF files from webpages,
with support for recursive link following, PDF merging, and various options.
"""

import argparse
import logging
import sys
from typing import Optional

from fetcharoo.fetcharoo import (
    download_pdfs_from_webpage,
    find_pdfs_from_webpage,
    set_default_user_agent,
)
from fetcharoo.filtering import FilterConfig

# Subcommands that the CLI recognizes
SUBCOMMANDS = {'diff', 'watch', 'catalog', 'schemas', 'mcp'}


def configure_logging(quiet: int, verbose: int) -> None:
    """
    Configure logging level based on quiet/verbose flags.

    Args:
        quiet: Number of -q flags (0, 1, or 2+)
        verbose: Number of -v flags (0, 1, or 2+)
    """
    # Get the fetcharoo logger
    logger = logging.getLogger('fetcharoo')

    # Calculate effective verbosity level
    # Default is WARNING, -q moves toward ERROR/CRITICAL, -v moves toward INFO/DEBUG
    verbosity = verbose - quiet

    if verbosity <= -2:
        level = logging.CRITICAL
    elif verbosity == -1:
        level = logging.ERROR
    elif verbosity == 0:
        level = logging.WARNING
    elif verbosity == 1:
        level = logging.INFO
    else:  # verbosity >= 2
        level = logging.DEBUG

    # Configure handler if needed
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        logger.addHandler(handler)

    logger.setLevel(level)


def create_download_parser() -> argparse.ArgumentParser:
    """
    Create the argument parser for the default download command.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        prog='fetcharoo',
        description='Download PDF files from webpages with optional recursive link following.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download PDFs from a single page
  fetcharoo https://example.com

  # Download with recursion depth 2 and merge into one file
  fetcharoo https://example.com -d 2 -m

  # List PDFs without downloading (dry run)
  fetcharoo https://example.com --dry-run

  # Download to custom directory with custom delay
  fetcharoo https://example.com -o my_pdfs --delay 1.0

  # Parallel download with 10 workers
  fetcharoo https://example.com --concurrent --max-workers 10

Subcommands:
  fetcharoo diff <url>          Check for new/changed PDFs since last run
  fetcharoo watch <url>         Continuously monitor a URL for changes
  fetcharoo catalog show        View tracked documents
  fetcharoo catalog export      Export catalog as JSON/CSV
  fetcharoo schemas list        List available site schemas
  fetcharoo mcp serve           Start the MCP server
        """
    )

    # Positional argument
    parser.add_argument(
        'url',
        type=str,
        help='URL of the webpage to search for PDFs'
    )

    # Optional arguments
    parser.add_argument(
        '-o', '--output',
        type=str,
        default='output',
        metavar='DIR',
        help='output directory for downloaded PDFs (default: output)'
    )

    parser.add_argument(
        '-d', '--depth',
        type=int,
        default=0,
        metavar='N',
        help='recursion depth for following links (default: 0)'
    )

    parser.add_argument(
        '-m', '--merge',
        action='store_true',
        help='merge all PDFs into a single file'
    )

    parser.add_argument(
        '--output-name',
        type=str,
        metavar='FILENAME',
        help='custom filename for merged PDF (only used with --merge)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='list PDFs that would be downloaded without actually downloading them'
    )

    parser.add_argument(
        '--delay',
        type=float,
        default=0.5,
        metavar='SECONDS',
        help='delay between requests in seconds (default: 0.5)'
    )

    parser.add_argument(
        '--timeout',
        type=int,
        default=30,
        metavar='SECONDS',
        help='request timeout in seconds (default: 30)'
    )

    parser.add_argument(
        '--user-agent',
        type=str,
        metavar='STRING',
        help='custom user agent string'
    )

    parser.add_argument(
        '--respect-robots',
        action='store_true',
        help='respect robots.txt rules when crawling'
    )

    parser.add_argument(
        '--progress',
        action='store_true',
        help='show progress bars during download'
    )

    # Concurrent download options
    parser.add_argument(
        '--concurrent',
        action='store_true',
        help='download PDFs in parallel using multiple threads'
    )

    parser.add_argument(
        '--max-workers',
        type=int,
        default=5,
        metavar='N',
        help='maximum concurrent download threads (default: 5, used with --concurrent)'
    )

    # Catalog option
    parser.add_argument(
        '--catalog',
        action='store_true',
        help='track downloaded documents in the persistent catalog'
    )

    parser.add_argument(
        '--catalog-db',
        type=str,
        metavar='PATH',
        help='path to catalog database file (default: ~/.fetcharoo/catalog.db)'
    )

    # Schema option
    parser.add_argument(
        '--schema',
        type=str,
        metavar='NAME',
        help='use a site schema (use "auto" for auto-detection, or a schema name)'
    )

    # Verbosity options
    parser.add_argument(
        '-q', '--quiet',
        action='count',
        default=0,
        help='reduce output verbosity (use -qq for even quieter)'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='count',
        default=0,
        help='increase output verbosity (use -vv for debug level)'
    )

    # Sorting options
    parser.add_argument(
        '--sort-by',
        type=str,
        choices=['none', 'numeric', 'alpha', 'alpha_desc'],
        default=None,
        metavar='STRATEGY',
        help='sort PDFs before merging: numeric (by numbers in filename), alpha (alphabetical), '
             'alpha_desc (reverse alphabetical), none (default, preserves discovery order)'
    )

    # Filtering options
    parser.add_argument(
        '--include',
        type=str,
        action='append',
        metavar='PATTERN',
        help='include PDFs matching filename pattern (can be used multiple times)'
    )

    parser.add_argument(
        '--exclude',
        type=str,
        action='append',
        metavar='PATTERN',
        help='exclude PDFs matching filename pattern (can be used multiple times)'
    )

    parser.add_argument(
        '--min-size',
        type=int,
        metavar='BYTES',
        help='minimum PDF size in bytes'
    )

    parser.add_argument(
        '--max-size',
        type=int,
        metavar='BYTES',
        help='maximum PDF size in bytes'
    )

    return parser


# Keep backward compatibility alias
def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser (alias for create_download_parser)."""
    return create_download_parser()


def _handle_diff(argv: list) -> int:
    """Handle the 'diff' subcommand."""
    from fetcharoo.catalog import DocumentCatalog
    from fetcharoo.watcher import diff_once
    from fetcharoo.notifications import has_changes

    parser = argparse.ArgumentParser(prog='fetcharoo diff', description='Check for new/changed PDFs since last run')
    parser.add_argument('url', type=str, help='URL to check for changes')
    parser.add_argument('-d', '--depth', type=int, default=0, help='recursion depth')
    parser.add_argument('--format', type=str, choices=['text', 'json'], default='text', help='output format')
    parser.add_argument('--catalog-db', type=str, metavar='PATH', help='catalog database path')
    parser.add_argument('--delay', type=float, default=0.5, help='request delay')
    parser.add_argument('--timeout', type=int, default=30, help='request timeout')
    parser.add_argument('--respect-robots', action='store_true', help='respect robots.txt')
    parser.add_argument('--user-agent', type=str, help='custom user agent')
    parser.add_argument('-q', '--quiet', action='count', default=0)
    parser.add_argument('-v', '--verbose', action='count', default=0)

    args = parser.parse_args(argv)
    configure_logging(args.quiet, args.verbose)
    if args.user_agent:
        set_default_user_agent(args.user_agent)

    catalog = DocumentCatalog(db_path=args.catalog_db)
    try:
        diff = diff_once(
            url=args.url,
            catalog=catalog,
            recursion_depth=args.depth,
            request_delay=args.delay,
            timeout=args.timeout,
            respect_robots=args.respect_robots,
            user_agent=args.user_agent,
            output_format=args.format,
        )
        return 0 if has_changes(diff) else 1
    finally:
        catalog.close()


def _handle_watch(argv: list) -> int:
    """Handle the 'watch' subcommand."""
    from fetcharoo.catalog import DocumentCatalog
    from fetcharoo.watcher import DocumentWatcher

    parser = argparse.ArgumentParser(prog='fetcharoo watch', description='Continuously monitor a URL for new/changed PDFs')
    parser.add_argument('url', type=str, help='URL to watch')
    parser.add_argument('-d', '--depth', type=int, default=0, help='recursion depth')
    parser.add_argument('--interval', type=float, default=3600, metavar='SECONDS', help='check interval (default: 3600)')
    parser.add_argument('--notify', type=str, choices=['stdout', 'json', 'webhook', 'command'], default='stdout', help='notification method')
    parser.add_argument('--webhook', type=str, metavar='URL', help='webhook URL')
    parser.add_argument('--on-command', type=str, metavar='CMD', help='shell command on change')
    parser.add_argument('--catalog-db', type=str, metavar='PATH', help='catalog database path')
    parser.add_argument('--delay', type=float, default=0.5, help='request delay')
    parser.add_argument('--timeout', type=int, default=30, help='request timeout')
    parser.add_argument('--respect-robots', action='store_true', help='respect robots.txt')
    parser.add_argument('--user-agent', type=str, help='custom user agent')
    parser.add_argument('-q', '--quiet', action='count', default=0)
    parser.add_argument('-v', '--verbose', action='count', default=0)

    args = parser.parse_args(argv)
    configure_logging(args.quiet, args.verbose)
    if args.user_agent:
        set_default_user_agent(args.user_agent)

    catalog = DocumentCatalog(db_path=args.catalog_db)
    try:
        watcher = DocumentWatcher(
            url=args.url,
            catalog=catalog,
            recursion_depth=args.depth,
            request_delay=args.delay,
            timeout=args.timeout,
            respect_robots=args.respect_robots,
            user_agent=args.user_agent,
        )
        watcher.watch(
            interval=args.interval,
            notify=args.notify,
            webhook_url=args.webhook,
            command=args.on_command,
        )
        return 0
    finally:
        catalog.close()


def _handle_catalog(argv: list) -> int:
    """Handle the 'catalog' subcommand."""
    from fetcharoo.catalog import DocumentCatalog

    if not argv:
        print("Usage: fetcharoo catalog {show|export|search|runs|duplicates}")
        return 1

    action = argv[0]
    rest = argv[1:]

    parser = argparse.ArgumentParser(prog=f'fetcharoo catalog {action}')
    parser.add_argument('--catalog-db', type=str, metavar='PATH', help='catalog database path')

    if action == 'show':
        parser.add_argument('--source', type=str, help='filter by source URL')
        args = parser.parse_args(rest)
        catalog = DocumentCatalog(db_path=args.catalog_db)
        try:
            docs = catalog.get_active_documents(source_page=args.source)
            if not docs:
                print("Catalog is empty.")
                return 0
            print(f"Tracked documents: {len(docs)}")
            for doc in docs:
                status_mark = {'active': ' ', 'removed': '-', 'changed': '~'}.get(doc.status, '?')
                size = f"{doc.size_bytes:,} bytes" if doc.size_bytes else "unknown size"
                print(f"  [{status_mark}] {doc.url}")
                print(f"      {doc.filename or 'unnamed'} | {size} | last seen: {doc.last_seen or 'never'}")
            return 0
        finally:
            catalog.close()

    elif action == 'export':
        parser.add_argument('--format', type=str, choices=['json', 'csv'], default='json', help='export format')
        args = parser.parse_args(rest)
        catalog = DocumentCatalog(db_path=args.catalog_db)
        try:
            if args.format == 'json':
                print(catalog.export_json())
            else:
                print(catalog.export_csv())
            return 0
        finally:
            catalog.close()

    elif action == 'search':
        parser.add_argument('query', type=str, help='search string')
        args = parser.parse_args(rest)
        catalog = DocumentCatalog(db_path=args.catalog_db)
        try:
            docs = catalog.search(args.query)
            if not docs:
                print(f"No documents matching '{args.query}'")
                return 1
            print(f"Found {len(docs)} document(s):")
            for doc in docs:
                print(f"  {doc.url} [{doc.status}]")
            return 0
        finally:
            catalog.close()

    elif action == 'runs':
        parser.add_argument('--limit', type=int, default=20, help='max runs to show')
        args = parser.parse_args(rest)
        catalog = DocumentCatalog(db_path=args.catalog_db)
        try:
            runs = catalog.get_runs(limit=args.limit)
            if not runs:
                print("No runs recorded.")
                return 0
            print(f"Recent runs ({len(runs)}):")
            for run in runs:
                print(f"  {run.timestamp} | {run.url}")
                print(f"    found={run.documents_found} new={run.documents_new} "
                      f"changed={run.documents_changed} removed={run.documents_removed}")
            return 0
        finally:
            catalog.close()

    elif action == 'duplicates':
        args = parser.parse_args(rest)
        catalog = DocumentCatalog(db_path=args.catalog_db)
        try:
            dupes = catalog.find_duplicates()
            if not dupes:
                print("No duplicate documents found.")
                return 0
            print(f"Found {len(dupes)} group(s) of duplicates:")
            for hash_val, docs in dupes.items():
                print(f"\n  Content hash: {hash_val[:16]}...")
                for doc in docs:
                    print(f"    {doc.url}")
            return 0
        finally:
            catalog.close()

    else:
        print(f"Unknown catalog action: {action}")
        print("Usage: fetcharoo catalog {show|export|search|runs|duplicates}")
        return 1


def _handle_schemas(argv: list) -> int:
    """Handle the 'schemas' subcommand."""
    from fetcharoo.schemas import find_schema, list_schemas

    if not argv:
        print("Usage: fetcharoo schemas {list|match <url>}")
        return 1

    action = argv[0]

    if action == 'list':
        schemas = list_schemas()
        if not schemas:
            print("No schemas available.")
            return 0
        print(f"Available schemas ({len(schemas)}):")
        for schema in schemas:
            print(f"  {schema.name:20s} {schema.description or ''}")
            print(f"  {'':20s} pattern: {schema.url_pattern}")
            print(f"  {'':20s} depth: {schema.recommended_depth}, delay: {schema.request_delay}s")
            print()
        return 0

    elif action == 'match':
        if len(argv) < 2:
            print("Usage: fetcharoo schemas match <url>")
            return 1
        url = argv[1]
        schema = find_schema(url)
        if schema:
            print(f"Matched schema: {schema.name}")
            print(f"  Description: {schema.description}")
            print(f"  Recommended depth: {schema.recommended_depth}")
            print(f"  Request delay: {schema.request_delay}s")
            if schema.include_patterns:
                print(f"  Include patterns: {schema.include_patterns}")
            if schema.exclude_patterns:
                print(f"  Exclude patterns: {schema.exclude_patterns}")
        else:
            print(f"No schema matches: {url}")
            return 1
        return 0

    else:
        print(f"Unknown schemas action: {action}")
        print("Usage: fetcharoo schemas {list|match <url>}")
        return 1


def _handle_mcp(argv: list) -> int:
    """Handle the 'mcp' subcommand."""
    if not argv or argv[0] != 'serve':
        print("Usage: fetcharoo mcp serve")
        return 1

    from fetcharoo.mcp_server import main as mcp_main
    mcp_main()
    return 0


def main(argv: Optional[list] = None) -> int:
    """
    Main entry point for the CLI.

    Args:
        argv: Command-line arguments (defaults to sys.argv if None).

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    if argv is None:
        argv = sys.argv[1:]

    # Route to subcommand if the first argument is a known subcommand
    if argv and argv[0] in SUBCOMMANDS:
        command = argv[0]
        rest = argv[1:]
        try:
            if command == 'diff':
                return _handle_diff(rest)
            elif command == 'watch':
                return _handle_watch(rest)
            elif command == 'catalog':
                return _handle_catalog(rest)
            elif command == 'schemas':
                return _handle_schemas(rest)
            elif command == 'mcp':
                return _handle_mcp(rest)
        except KeyboardInterrupt:
            print("\n\nOperation cancelled by user.")
            return 1
        except Exception as e:
            print(f"\nError: {e}", file=sys.stderr)
            return 1

    # Default: download command
    parser = create_download_parser()

    if not argv:
        parser.print_help()
        sys.exit(2)

    args = parser.parse_args(argv)

    # Configure logging based on verbosity flags
    configure_logging(args.quiet, args.verbose)

    # Set custom user agent if provided
    if args.user_agent:
        set_default_user_agent(args.user_agent)

    # Auto-detect or apply schema
    if args.schema:
        from fetcharoo.schemas import find_schema, list_schemas
        if args.schema == 'auto':
            schema = find_schema(args.url)
        else:
            schemas = list_schemas()
            schema = next((s for s in schemas if s.name == args.schema), None)

        if schema:
            print(f"Using schema: {schema.name}")
            if args.depth == 0 and schema.recommended_depth > 0:
                args.depth = schema.recommended_depth
            if args.delay == 0.5 and schema.request_delay != 0.5:
                args.delay = schema.request_delay
            if args.sort_by is None and schema.sort_by:
                args.sort_by = schema.sort_by
            if not args.include and not args.exclude:
                schema_filter = schema.get_filter_config()
                if schema_filter:
                    args.include = schema_filter.filename_include or None
                    args.exclude = schema_filter.filename_exclude or None

    # Build filter config if any filtering options are provided
    filter_config = None
    if args.include or args.exclude or args.min_size or args.max_size:
        filter_config = FilterConfig(
            filename_include=args.include or [],
            filename_exclude=args.exclude or [],
            min_size=args.min_size,
            max_size=args.max_size
        )

    # Determine mode based on merge flag
    mode = 'merge' if args.merge else 'separate'

    try:
        # Handle dry-run mode
        if args.dry_run:
            print(f"Searching for PDFs at: {args.url}")
            print(f"Recursion depth: {args.depth}")
            if args.respect_robots:
                print("Respecting robots.txt rules")
            print()

            pdf_links = find_pdfs_from_webpage(
                args.url,
                recursion_depth=args.depth,
                request_delay=args.delay,
                timeout=args.timeout,
                respect_robots=args.respect_robots,
                user_agent=args.user_agent,
                show_progress=args.progress
            )

            if pdf_links:
                print(f"Found {len(pdf_links)} PDF(s):")
                for i, link in enumerate(pdf_links, 1):
                    print(f"  {i}. {link}")
            else:
                print("No PDFs found.")

            return 0

        # Normal download mode
        print(f"Downloading PDFs from: {args.url}")
        print(f"Output directory: {args.output}")
        print(f"Recursion depth: {args.depth}")
        print(f"Mode: {mode}")
        if args.concurrent:
            print(f"Concurrent: {args.max_workers} workers")
        if args.respect_robots:
            print("Respecting robots.txt rules")
        if filter_config:
            print("Filtering enabled")
        print()

        result = download_pdfs_from_webpage(
            args.url,
            recursion_depth=args.depth,
            mode=mode,
            write_dir=args.output,
            request_delay=args.delay,
            timeout=args.timeout,
            respect_robots=args.respect_robots,
            user_agent=args.user_agent,
            dry_run=False,
            show_progress=args.progress,
            filter_config=filter_config,
            sort_by=args.sort_by,
            output_name=args.output_name,
            concurrent=args.concurrent,
            max_workers=args.max_workers,
        )

        # Optionally record in catalog
        if args.catalog and result:
            from fetcharoo.catalog import DocumentCatalog
            catalog = DocumentCatalog(db_path=args.catalog_db)
            try:
                pdf_links = find_pdfs_from_webpage(
                    args.url,
                    recursion_depth=args.depth,
                    request_delay=args.delay,
                    timeout=args.timeout,
                )
                for link in pdf_links:
                    catalog.record_discovery(link, source_page=args.url)
                print(f"Recorded {len(pdf_links)} document(s) in catalog.")
            finally:
                catalog.close()

        if result:
            print(f"\nSuccessfully downloaded PDFs to: {args.output}")
            return 0
        else:
            print("\nNo PDFs were downloaded.")
            return 1

    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        return 1
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
