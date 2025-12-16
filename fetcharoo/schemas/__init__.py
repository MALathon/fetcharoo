"""
Site-specific download schemas for fetcharoo.

This package provides the schema system for defining site-specific
PDF download configurations. Schemas encapsulate the best practices
for downloading PDFs from different websites.

Example:
    >>> from fetcharoo.schemas import SiteSchema, register_schema, detect_schema
    >>>
    >>> # Create and register a schema
    >>> schema = SiteSchema(
    ...     name='my_site',
    ...     url_pattern=r'https://mysite\\.com/.*',
    ...     sort_by='numeric'
    ... )
    >>> register_schema(schema)
    >>>
    >>> # Auto-detect schema from URL
    >>> detected = detect_schema('https://mysite.com/docs')
    >>> print(detected.name)
    'my_site'
"""

from fetcharoo.schemas.base import SiteSchema
from fetcharoo.schemas.registry import (
    register_schema,
    unregister_schema,
    get_schema,
    detect_schema,
    list_schemas,
    get_all_schemas,
    clear_registry,
    schema,
    is_registered,
    schema_count,
)

__all__ = [
    # Base class
    "SiteSchema",
    # Registry functions
    "register_schema",
    "unregister_schema",
    "get_schema",
    "detect_schema",
    "list_schemas",
    "get_all_schemas",
    "clear_registry",
    "schema",
    "is_registered",
    "schema_count",
]
