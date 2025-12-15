"""
Command-line interface for fetcharoo.

This module provides a CLI for downloading PDF files from webpages,
with support for recursive link following, PDF merging, and various options.
"""

import argparse
import sys
from typing import Optional

from fetcharoo.fetcharoo import (
    download_pdfs_from_webpage,
    find_pdfs_from_webpage,
    set_default_user_agent,
)
from fetcharoo.filtering import FilterConfig


def create_parser() -> argparse.ArgumentParser:
    """
    Create and configure the argument parser for the CLI.

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


def main(argv: Optional[list] = None) -> int:
    """
    Main entry point for the CLI.

    Args:
        argv: Command-line arguments (defaults to sys.argv if None).

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    parser = create_parser()

    # Parse arguments
    args = parser.parse_args(argv)

    # Set custom user agent if provided
    if args.user_agent:
        set_default_user_agent(args.user_agent)

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
        if args.respect_robots:
            print("Respecting robots.txt rules")
        if filter_config:
            print("Filtering enabled")
        print()

        success = download_pdfs_from_webpage(
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
            output_name=args.output_name
        )

        if success:
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
