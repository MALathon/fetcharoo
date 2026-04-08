"""
Site-specific download schemas for fetcharoo.

This package provides the schema system for defining site-specific
PDF download configurations. Schemas encapsulate the best practices
for downloading PDFs from different websites.

Example:
    >>> from fetcharoo.schemas import SiteSchema, find_schema
    >>> schema = SiteSchema(
    ...     name='my_site',
    ...     url_pattern=r'https://mysite\\.com/.*',
    ...     sort_by='numeric'
    ... )
    >>> schema.matches('https://mysite.com/docs')
    True
"""

from typing import List, Optional

from fetcharoo.schemas.base import SiteSchema


def find_schema(url: str) -> Optional[SiteSchema]:
    """
    Find a built-in schema that matches the given URL.

    Args:
        url: The URL to match against registered schemas.

    Returns:
        The first matching SiteSchema, or None if no match found.
    """
    from fetcharoo.schemas.sites import BUILTIN_SCHEMAS
    for schema in BUILTIN_SCHEMAS:
        if schema.matches(url):
            return schema
    return None


def list_schemas() -> List[SiteSchema]:
    """
    List all available built-in schemas.

    Returns:
        List of all registered SiteSchema instances.
    """
    from fetcharoo.schemas.sites import BUILTIN_SCHEMAS
    return list(BUILTIN_SCHEMAS)


__all__ = [
    "SiteSchema",
    "find_schema",
    "list_schemas",
]
