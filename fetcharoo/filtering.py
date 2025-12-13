"""
PDF filtering functionality for fetcharoo.

This module provides filtering capabilities for PDFs including:
- Filename pattern matching (include/exclude)
- File size filtering (min/max)
- URL pattern filtering
- Combined filter logic

Author: Mark A. Lifson, Ph.D.
"""

import fnmatch
import os
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import urlparse


@dataclass
class FilterConfig:
    """
    Configuration for PDF filtering.

    Attributes:
        filename_include: List of filename patterns to include (e.g., ['report*.pdf']).
                         Empty list means no filtering by filename.
        filename_exclude: List of filename patterns to exclude (e.g., ['*draft*']).
                         Exclude patterns override include patterns.
        min_size: Minimum file size in bytes. None means no minimum.
        max_size: Maximum file size in bytes. None means no maximum.
        url_include: List of URL patterns to include (e.g., ['*/reports/*']).
                    Empty list means no filtering by URL.
        url_exclude: List of URL patterns to exclude (e.g., ['*/temp/*']).
                    Exclude patterns override include patterns.
    """
    filename_include: List[str] = field(default_factory=list)
    filename_exclude: List[str] = field(default_factory=list)
    min_size: Optional[int] = None
    max_size: Optional[int] = None
    url_include: List[str] = field(default_factory=list)
    url_exclude: List[str] = field(default_factory=list)


def matches_filename_pattern(
    filename: str,
    include_patterns: List[str],
    exclude_patterns: List[str]
) -> bool:
    """
    Check if a filename matches the include/exclude patterns.

    Pattern matching is case-insensitive and uses fnmatch syntax:
    - * matches everything
    - ? matches any single character
    - [seq] matches any character in seq
    - [!seq] matches any character not in seq

    Args:
        filename: The filename to check (e.g., 'report_2023.pdf').
        include_patterns: List of patterns to include. If empty, all filenames match.
        exclude_patterns: List of patterns to exclude. Exclude overrides include.

    Returns:
        True if the filename should be included, False otherwise.
    """
    # Normalize filename to lowercase for case-insensitive matching
    filename_lower = filename.lower()

    # First check exclude patterns - these override include patterns
    for pattern in exclude_patterns:
        if fnmatch.fnmatch(filename_lower, pattern.lower()):
            return False

    # If no include patterns specified, accept all (that weren't excluded)
    if not include_patterns:
        return True

    # Check if filename matches any include pattern
    for pattern in include_patterns:
        if fnmatch.fnmatch(filename_lower, pattern.lower()):
            return True

    return False


def matches_size_limits(
    size_bytes: Optional[int],
    min_size: Optional[int],
    max_size: Optional[int]
) -> bool:
    """
    Check if a file size is within the specified limits.

    Args:
        size_bytes: The file size in bytes. None if size is unknown.
        min_size: Minimum file size in bytes. None means no minimum.
        max_size: Maximum file size in bytes. None means no maximum.

    Returns:
        True if the file size is within limits, False otherwise.
        Returns True if size_bytes is None (size unknown - skip size check).
        Returns False if size_bytes is negative.
    """
    # If size is unknown, skip size filtering
    if size_bytes is None:
        return True

    # Reject negative sizes
    if size_bytes < 0:
        return False

    # Check minimum size
    if min_size is not None and size_bytes < min_size:
        return False

    # Check maximum size
    if max_size is not None and size_bytes > max_size:
        return False

    return True


def matches_url_pattern(
    url: str,
    include_patterns: List[str],
    exclude_patterns: List[str]
) -> bool:
    """
    Check if a URL matches the include/exclude patterns.

    Pattern matching uses fnmatch syntax and is applied to the full URL.

    Args:
        url: The URL to check (e.g., 'https://example.com/reports/annual.pdf').
        include_patterns: List of URL patterns to include. If empty, all URLs match.
        exclude_patterns: List of URL patterns to exclude. Exclude overrides include.

    Returns:
        True if the URL should be included, False otherwise.
    """
    # Normalize URL to lowercase for case-insensitive matching
    url_lower = url.lower()

    # First check exclude patterns - these override include patterns
    for pattern in exclude_patterns:
        if fnmatch.fnmatch(url_lower, pattern.lower()):
            return False

    # If no include patterns specified, accept all (that weren't excluded)
    if not include_patterns:
        return True

    # Check if URL matches any include pattern
    for pattern in include_patterns:
        if fnmatch.fnmatch(url_lower, pattern.lower()):
            return True

    return False


def apply_filters(
    pdf_url: str,
    size_bytes: Optional[int],
    filter_config: Optional[FilterConfig]
) -> bool:
    """
    Apply all configured filters to determine if a PDF should be downloaded.

    This function combines filename, size, and URL filtering logic.
    All filters must pass for the PDF to be accepted.

    Args:
        pdf_url: The URL of the PDF file.
        size_bytes: The file size in bytes. None if size is unknown.
        filter_config: The filter configuration. None means no filtering.

    Returns:
        True if the PDF passes all filters and should be downloaded, False otherwise.
    """
    # If no filter config, accept all PDFs
    if filter_config is None:
        return True

    # Extract filename from URL
    parsed_url = urlparse(pdf_url)
    filename = os.path.basename(parsed_url.path)

    # Apply filename pattern filter
    if not matches_filename_pattern(
        filename,
        filter_config.filename_include,
        filter_config.filename_exclude
    ):
        return False

    # Apply size filter
    if not matches_size_limits(
        size_bytes,
        filter_config.min_size,
        filter_config.max_size
    ):
        return False

    # Apply URL pattern filter
    if not matches_url_pattern(
        pdf_url,
        filter_config.url_include,
        filter_config.url_exclude
    ):
        return False

    return True


def should_download_pdf(
    pdf_url: str,
    size_bytes: Optional[int] = None,
    filter_config: Optional[FilterConfig] = None
) -> bool:
    """
    Convenience function to check if a PDF should be downloaded.

    This is an alias for apply_filters with a more intuitive name.

    Args:
        pdf_url: The URL of the PDF file.
        size_bytes: The file size in bytes. None if size is unknown.
        filter_config: The filter configuration. None means no filtering.

    Returns:
        True if the PDF should be downloaded, False otherwise.
    """
    return apply_filters(pdf_url, size_bytes, filter_config)
