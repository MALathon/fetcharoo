"""
Document change monitoring for fetcharoo.

Provides watch mode to detect new, changed, and removed PDFs on a website.
Supports one-shot diff (cron-friendly) and continuous watch modes.
"""

import logging
import signal
import time
from typing import List, Optional

from fetcharoo.catalog import DiffResult, DocumentCatalog
from fetcharoo.fetcharoo import find_pdfs_from_webpage
from fetcharoo.notifications import (
    format_diff_json,
    format_diff_text,
    has_changes,
    notify_command,
    notify_json,
    notify_stdout,
    notify_webhook,
)

logger = logging.getLogger('fetcharoo')


class DocumentWatcher:
    """
    Watches a URL for document changes over time.

    Uses a DocumentCatalog for persistent state and supports
    multiple notification methods.
    """

    def __init__(
        self,
        url: str,
        catalog: DocumentCatalog,
        recursion_depth: int = 0,
        request_delay: float = 0.5,
        timeout: int = 30,
        respect_robots: bool = False,
        user_agent: Optional[str] = None,
    ):
        self.url = url
        self.catalog = catalog
        self.recursion_depth = recursion_depth
        self.request_delay = request_delay
        self.timeout = timeout
        self.respect_robots = respect_robots
        self.user_agent = user_agent
        self._stop = False

    def check_once(self) -> DiffResult:
        """
        Perform a single check: crawl the URL, compare against catalog.

        Returns:
            DiffResult with new, changed, removed, unchanged documents.
        """
        # Discover current PDFs
        current_urls = find_pdfs_from_webpage(
            self.url,
            recursion_depth=self.recursion_depth,
            request_delay=self.request_delay,
            timeout=self.timeout,
            respect_robots=self.respect_robots,
            user_agent=self.user_agent,
        )

        # Compare against catalog
        diff = self.catalog.diff(current_urls)

        # Update catalog with new discoveries
        for doc in diff.new:
            self.catalog.record_discovery(
                doc.url, source_page=self.url
            )

        # Mark removed documents
        for doc in diff.removed:
            self.catalog.mark_removed(doc.url)

        # Record the run
        self.catalog.record_run(self.url, diff)

        return diff

    def watch(
        self,
        interval: float = 3600,
        notify: str = 'stdout',
        webhook_url: Optional[str] = None,
        command: Optional[str] = None,
        on_change_only: bool = True,
    ) -> None:
        """
        Continuously watch for changes at a regular interval.

        Args:
            interval: Seconds between checks.
            notify: Notification method ('stdout', 'json', 'webhook', 'command').
            webhook_url: URL for webhook notifications.
            command: Shell command for command notifications.
            on_change_only: If True, only notify when changes are detected.
        """
        # Handle graceful shutdown
        def _signal_handler(signum, frame):
            self._stop = True

        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)

        logger.info(f"Watching {self.url} every {interval}s (Ctrl+C to stop)")
        print(f"Watching {self.url} every {interval:.0f}s (Ctrl+C to stop)")

        while not self._stop:
            try:
                diff = self.check_once()

                if not on_change_only or has_changes(diff):
                    self._notify(diff, notify, webhook_url, command)

                if not self._stop:
                    time.sleep(interval)

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Watch error: {e}")
                if not self._stop:
                    time.sleep(interval)

        print("\nWatch stopped.")

    def _notify(
        self,
        diff: DiffResult,
        method: str,
        webhook_url: Optional[str] = None,
        command: Optional[str] = None,
    ) -> None:
        """Dispatch notification to the appropriate handler."""
        if method == 'stdout':
            notify_stdout(diff, self.url)
        elif method == 'json':
            notify_json(diff, self.url)
        elif method == 'webhook' and webhook_url:
            notify_webhook(diff, self.url, webhook_url)
        elif method == 'command' and command:
            notify_command(diff, self.url, command)
        else:
            notify_stdout(diff, self.url)


def diff_once(
    url: str,
    catalog: DocumentCatalog,
    recursion_depth: int = 0,
    request_delay: float = 0.5,
    timeout: int = 30,
    respect_robots: bool = False,
    user_agent: Optional[str] = None,
    output_format: str = 'text',
) -> DiffResult:
    """
    One-shot diff: compare current state against catalog and print results.

    Designed for cron jobs. Returns appropriate exit-code-friendly result.

    Args:
        url: The URL to check.
        catalog: The DocumentCatalog instance.
        recursion_depth: Crawl depth.
        request_delay: Delay between requests.
        timeout: Request timeout.
        respect_robots: Whether to respect robots.txt.
        user_agent: Custom user agent.
        output_format: 'text' or 'json'.

    Returns:
        The DiffResult.
    """
    watcher = DocumentWatcher(
        url=url,
        catalog=catalog,
        recursion_depth=recursion_depth,
        request_delay=request_delay,
        timeout=timeout,
        respect_robots=respect_robots,
        user_agent=user_agent,
    )

    diff = watcher.check_once()

    if output_format == 'json':
        print(format_diff_json(diff, url))
    else:
        print(format_diff_text(diff, url))

    return diff
