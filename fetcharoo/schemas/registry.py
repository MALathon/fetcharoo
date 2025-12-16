"""
Schema registry for managing site-specific download configurations.

This module provides a global registry for storing and retrieving schemas,
with support for auto-detection based on URL patterns.
"""

import logging
from typing import Dict, List, Optional, Union

from fetcharoo.schemas.base import SiteSchema

logger = logging.getLogger('fetcharoo.schemas')

# Global schema registry
_SCHEMAS: Dict[str, SiteSchema] = {}


def register_schema(schema: SiteSchema, overwrite: bool = False) -> None:
    """
    Register a schema in the global registry.

    Args:
        schema: The SiteSchema instance to register.
        overwrite: If True, overwrite existing schema with same name.
                  If False (default), raise ValueError if name exists.

    Raises:
        ValueError: If schema name already exists and overwrite=False.
        TypeError: If schema is not a SiteSchema instance.

    Example:
        >>> schema = SiteSchema(name='my_site', url_pattern=r'https://mysite\\.com/.*')
        >>> register_schema(schema)
    """
    if not isinstance(schema, SiteSchema):
        raise TypeError(f"Expected SiteSchema, got {type(schema).__name__}")

    if schema.name in _SCHEMAS and not overwrite:
        raise ValueError(
            f"Schema '{schema.name}' already registered. "
            f"Use overwrite=True to replace it."
        )

    _SCHEMAS[schema.name] = schema
    logger.debug(f"Registered schema: {schema.name}")


def unregister_schema(name: str) -> bool:
    """
    Remove a schema from the registry.

    Args:
        name: The name of the schema to remove.

    Returns:
        True if schema was removed, False if it wasn't registered.

    Example:
        >>> unregister_schema('my_site')
        True
    """
    if name in _SCHEMAS:
        del _SCHEMAS[name]
        logger.debug(f"Unregistered schema: {name}")
        return True
    return False


def get_schema(name: str) -> Optional[SiteSchema]:
    """
    Get a schema by name.

    Args:
        name: The name of the schema to retrieve.

    Returns:
        The SiteSchema instance, or None if not found.

    Example:
        >>> schema = get_schema('springer_book')
        >>> if schema:
        ...     print(schema.description)
    """
    return _SCHEMAS.get(name)


def detect_schema(url: str) -> Optional[SiteSchema]:
    """
    Auto-detect schema from URL by testing all registered patterns.

    Iterates through registered schemas and returns the first one
    whose URL pattern matches the given URL. More specific patterns
    should be registered before generic ones to ensure correct matching.

    Args:
        url: The URL to match against schema patterns.

    Returns:
        The first matching SiteSchema, or None if no match.

    Example:
        >>> schema = detect_schema('https://link.springer.com/book/10.1007/978-3-031-41026-0')
        >>> if schema:
        ...     print(f"Detected: {schema.name}")
    """
    for schema in _SCHEMAS.values():
        if schema.matches(url):
            logger.debug(f"Auto-detected schema '{schema.name}' for URL: {url}")
            return schema
    return None


def list_schemas() -> List[str]:
    """
    List all registered schema names.

    Returns:
        A sorted list of registered schema names.

    Example:
        >>> names = list_schemas()
        >>> print(names)
        ['arxiv', 'generic', 'springer_book']
    """
    return sorted(_SCHEMAS.keys())


def get_all_schemas() -> Dict[str, SiteSchema]:
    """
    Get all registered schemas.

    Returns:
        A copy of the schema registry dictionary.

    Example:
        >>> schemas = get_all_schemas()
        >>> for name, schema in schemas.items():
        ...     print(f"{name}: {schema.description}")
    """
    return _SCHEMAS.copy()


def clear_registry() -> None:
    """
    Clear all schemas from the registry.

    This is mainly useful for testing to ensure a clean state.

    Example:
        >>> clear_registry()
        >>> list_schemas()
        []
    """
    _SCHEMAS.clear()
    logger.debug("Cleared schema registry")


def schema(cls_or_instance: Union[type, SiteSchema]):
    """
    Decorator to register a schema class or instance.

    Can be used as a decorator on a class that inherits from SiteSchema,
    or called directly with a SiteSchema instance.

    Args:
        cls_or_instance: Either a SiteSchema subclass or instance.

    Returns:
        The original class or instance (for use as decorator).

    Example:
        >>> # As class decorator
        >>> @schema
        ... class MySchema(SiteSchema):
        ...     name = 'my_schema'
        ...     url_pattern = r'https://mysite\\.com/.*'

        >>> # With instance
        >>> @schema
        ... class AnotherSchema(SiteSchema):
        ...     def __init__(self):
        ...         super().__init__(
        ...             name='another',
        ...             url_pattern=r'.*'
        ...         )
    """
    if isinstance(cls_or_instance, SiteSchema):
        # Direct instance
        register_schema(cls_or_instance)
        return cls_or_instance
    elif isinstance(cls_or_instance, type) and issubclass(cls_or_instance, SiteSchema):
        # Class - instantiate and register
        instance = cls_or_instance()
        register_schema(instance)
        return cls_or_instance
    else:
        raise TypeError(
            f"@schema decorator expects SiteSchema class or instance, "
            f"got {type(cls_or_instance).__name__}"
        )


def is_registered(name: str) -> bool:
    """
    Check if a schema is registered.

    Args:
        name: The schema name to check.

    Returns:
        True if the schema is registered, False otherwise.

    Example:
        >>> is_registered('springer_book')
        True
        >>> is_registered('nonexistent')
        False
    """
    return name in _SCHEMAS


def schema_count() -> int:
    """
    Get the number of registered schemas.

    Returns:
        The count of registered schemas.

    Example:
        >>> schema_count()
        3
    """
    return len(_SCHEMAS)
