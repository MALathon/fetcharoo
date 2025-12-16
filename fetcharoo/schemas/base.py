"""
Base schema class for site-specific download configurations.

This module provides the SiteSchema dataclass that defines the structure
for site-specific PDF download configurations.
"""

import re
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from fetcharoo.filtering import FilterConfig


@dataclass
class SiteSchema:
    """
    Base class for site-specific download configurations.

    A SiteSchema encapsulates the best way to download PDFs from a specific
    website or type of website. It includes URL pattern matching, PDF filtering,
    sorting strategies, and validation settings.

    Attributes:
        name: Unique identifier for this schema (e.g., 'springer_book').
        url_pattern: Regex pattern to match URLs this schema handles.
        description: Human-readable description of what this schema is for.
        include_patterns: Filename patterns to include (fnmatch syntax).
        exclude_patterns: Filename patterns to exclude (fnmatch syntax).
        url_include_patterns: URL patterns to include.
        url_exclude_patterns: URL patterns to exclude.
        sort_by: Sort strategy for merging: 'numeric', 'alpha', 'alpha_desc', 'none'.
        sort_key: Custom sort key function (takes URL, returns sortable value).
        default_output_name: Default filename for merged PDFs.
        recommended_depth: Suggested recursion depth for this site.
        request_delay: Suggested delay between requests in seconds.
        test_url: Sample URL for validation testing.
        expected_min_pdfs: Minimum PDFs expected when validating test_url.
        version: Schema version string for tracking updates.

    Example:
        >>> schema = SiteSchema(
        ...     name='example_site',
        ...     url_pattern=r'https?://example\\.com/docs/.*',
        ...     description='Example documentation site',
        ...     sort_by='numeric',
        ...     recommended_depth=1
        ... )
        >>> schema.matches('https://example.com/docs/guide')
        True
    """

    # Required fields
    name: str
    url_pattern: str

    # Description
    description: Optional[str] = None

    # PDF filtering patterns
    include_patterns: List[str] = field(default_factory=list)
    exclude_patterns: List[str] = field(default_factory=list)
    url_include_patterns: List[str] = field(default_factory=list)
    url_exclude_patterns: List[str] = field(default_factory=list)

    # Sorting
    sort_by: Optional[str] = None
    sort_key: Optional[Callable[[str], any]] = field(default=None, repr=False)

    # Output
    default_output_name: Optional[str] = None

    # Behavior
    recommended_depth: int = 1
    request_delay: float = 0.5

    # Validation
    test_url: Optional[str] = None
    expected_min_pdfs: int = 1

    # Metadata
    version: str = "1.0.0"

    # Compiled regex (cached)
    _compiled_pattern: Optional[re.Pattern] = field(
        default=None, init=False, repr=False, compare=False
    )

    def __post_init__(self):
        """Compile the URL pattern regex after initialization."""
        if self.url_pattern:
            try:
                self._compiled_pattern = re.compile(self.url_pattern)
            except re.error as e:
                raise ValueError(f"Invalid url_pattern regex: {e}")

        # Validate sort_by
        valid_sort_options = (None, 'none', 'numeric', 'alpha', 'alpha_desc')
        if self.sort_by not in valid_sort_options:
            raise ValueError(
                f"sort_by must be one of {valid_sort_options}, got '{self.sort_by}'"
            )

    def matches(self, url: str) -> bool:
        """
        Check if this schema matches the given URL.

        Args:
            url: The URL to check against this schema's pattern.

        Returns:
            True if the URL matches this schema's url_pattern, False otherwise.
        """
        if self._compiled_pattern is None:
            return False
        return bool(self._compiled_pattern.match(url))

    def get_filter_config(self) -> Optional[FilterConfig]:
        """
        Convert this schema's filter patterns to a FilterConfig.

        Returns:
            A FilterConfig instance if any filter patterns are defined,
            None if no filtering is configured.
        """
        has_filters = (
            self.include_patterns
            or self.exclude_patterns
            or self.url_include_patterns
            or self.url_exclude_patterns
        )

        if not has_filters:
            return None

        return FilterConfig(
            filename_include=self.include_patterns.copy(),
            filename_exclude=self.exclude_patterns.copy(),
            url_include=self.url_include_patterns.copy(),
            url_exclude=self.url_exclude_patterns.copy(),
        )

    def get_sort_key(self) -> Optional[Callable[[str], any]]:
        """
        Get the sort key function for this schema.

        Returns the custom sort_key if defined, otherwise returns a default
        sort key function based on the sort_by strategy.

        Returns:
            A callable sort key function, or None if no sorting is configured.
        """
        if self.sort_key is not None:
            return self.sort_key

        # Return None if no sorting strategy
        if self.sort_by is None or self.sort_by == 'none':
            return None

        # Default sort keys are handled by the caller (fetcharoo.py)
        # This allows the schema to just specify sort_by without a custom key
        return None

    def __str__(self) -> str:
        """Return a human-readable string representation."""
        desc = self.description or "No description"
        return f"{self.name}: {desc}"
