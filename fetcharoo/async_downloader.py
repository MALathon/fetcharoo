"""
Concurrent PDF downloading for fetcharoo.

This module provides parallel download capabilities using ThreadPoolExecutor,
allowing multiple PDFs to be downloaded simultaneously with configurable
concurrency limits and shared rate limiting.
"""

import logging
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple

from fetcharoo.downloader import download_pdf

logger = logging.getLogger('fetcharoo')


class RateLimiter:
    """Thread-safe rate limiter using token bucket algorithm."""

    def __init__(self, min_interval: float = 0.5):
        """
        Args:
            min_interval: Minimum seconds between requests.
        """
        self._min_interval = min_interval
        self._last_request = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        """Block until enough time has passed since the last request."""
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request
            if elapsed < self._min_interval:
                time.sleep(self._min_interval - elapsed)
            self._last_request = time.monotonic()


def download_pdfs_concurrent(
    pdf_links: List[str],
    max_workers: int = 5,
    timeout: int = 30,
    user_agent: Optional[str] = None,
    request_delay: float = 0.1,
    progress_callback: Optional[callable] = None,
) -> List[Tuple[Optional[bytes], str]]:
    """
    Download multiple PDFs concurrently using a thread pool.

    Args:
        pdf_links: List of PDF URLs to download.
        max_workers: Maximum number of concurrent download threads.
        timeout: Request timeout in seconds per download.
        user_agent: Custom User-Agent string.
        request_delay: Minimum delay between requests (shared across workers).
        progress_callback: Optional callable invoked after each download completes.
                          Called with no arguments.

    Returns:
        List of (content, url) tuples in the same order as pdf_links.
        content is bytes on success or None on failure.
    """
    if not pdf_links:
        return []

    rate_limiter = RateLimiter(min_interval=request_delay)
    results: Dict[int, Tuple[Optional[bytes], str]] = {}

    def _download_one(index: int, url: str) -> Tuple[int, Optional[bytes], str]:
        rate_limiter.wait()
        content = download_pdf(url, timeout=timeout, user_agent=user_agent)
        return index, content, url

    # Cap workers to number of links
    actual_workers = min(max_workers, len(pdf_links))

    with ThreadPoolExecutor(max_workers=actual_workers) as executor:
        futures = {
            executor.submit(_download_one, i, url): i
            for i, url in enumerate(pdf_links)
        }

        for future in as_completed(futures):
            try:
                index, content, url = future.result()
                results[index] = (content, url)
            except Exception as e:
                idx = futures[future]
                url = pdf_links[idx]
                logger.error(f"Unexpected error downloading {url}: {e}")
                results[idx] = (None, url)

            if progress_callback:
                progress_callback()

    # Return in original order
    return [results[i] for i in range(len(pdf_links))]
