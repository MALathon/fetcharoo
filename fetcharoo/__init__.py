"""
fetcharoo - A Python library for downloading PDF files from webpages.

This library provides tools for finding and downloading PDF files from webpages,
with support for recursive link following, PDF merging, and configurable options.
"""

from fetcharoo.fetcharoo import (
    download_pdfs_from_webpage,
    find_pdfs_from_webpage,
    process_pdfs,
    is_valid_url,
    is_safe_domain,
    sanitize_filename,
    check_robots_txt,
    set_default_user_agent,
    get_default_user_agent,
    SORT_BY_OPTIONS,
    ProcessResult,
)
from fetcharoo.pdf_utils import merge_pdfs, save_pdf_to_file
from fetcharoo.downloader import download_pdf
from fetcharoo.file_utils import check_file_exists, check_pdf_exists
from fetcharoo.filtering import (
    FilterConfig,
    matches_filename_pattern,
    matches_size_limits,
    matches_url_pattern,
    apply_filters,
    should_download_pdf,
)

__version__ = "0.1.0"

__all__ = [
    # Main API
    "download_pdfs_from_webpage",
    "find_pdfs_from_webpage",
    "process_pdfs",
    # PDF utilities
    "merge_pdfs",
    "save_pdf_to_file",
    "download_pdf",
    # File utilities
    "check_file_exists",
    "check_pdf_exists",
    # Validation & Security
    "is_valid_url",
    "is_safe_domain",
    "sanitize_filename",
    "check_robots_txt",
    # User-Agent customization
    "set_default_user_agent",
    "get_default_user_agent",
    # Sorting
    "SORT_BY_OPTIONS",
    # Result types
    "ProcessResult",
    # Filtering
    "FilterConfig",
    "matches_filename_pattern",
    "matches_size_limits",
    "matches_url_pattern",
    "apply_filters",
    "should_download_pdf",
    # Version
    "__version__",
]
