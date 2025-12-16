"""
Site-specific download schemas for fetcharoo.

This package provides the schema system for defining site-specific
PDF download configurations. Schemas encapsulate the best practices
for downloading PDFs from different websites.

Example:
    >>> from fetcharoo.schemas import SiteSchema
    >>> schema = SiteSchema(
    ...     name='my_site',
    ...     url_pattern=r'https://mysite\\.com/.*',
    ...     sort_by='numeric'
    ... )
    >>> schema.matches('https://mysite.com/docs')
    True
"""

from fetcharoo.schemas.base import SiteSchema

__all__ = [
    "SiteSchema",
]
