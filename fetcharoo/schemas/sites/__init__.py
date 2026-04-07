"""
Community site schemas for fetcharoo.

Pre-built download configurations for common document repositories.
"""

from fetcharoo.schemas.sites.arxiv import ARXIV_SCHEMA
from fetcharoo.schemas.sites.ietf_rfc import IETF_RFC_SCHEMA
from fetcharoo.schemas.sites.sec_edgar import SEC_EDGAR_SCHEMA
from fetcharoo.schemas.sites.w3c import W3C_SCHEMA
from fetcharoo.schemas.sites.federal_register import FEDERAL_REGISTER_SCHEMA

# Registry of all built-in schemas
BUILTIN_SCHEMAS = [
    ARXIV_SCHEMA,
    IETF_RFC_SCHEMA,
    SEC_EDGAR_SCHEMA,
    W3C_SCHEMA,
    FEDERAL_REGISTER_SCHEMA,
]

__all__ = [
    "ARXIV_SCHEMA",
    "IETF_RFC_SCHEMA",
    "SEC_EDGAR_SCHEMA",
    "W3C_SCHEMA",
    "FEDERAL_REGISTER_SCHEMA",
    "BUILTIN_SCHEMAS",
]
