"""
Tests for the schema registry module.
"""

import unittest
from fetcharoo.schemas import (
    SiteSchema,
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


class TestSchemaRegistryBase(unittest.TestCase):
    """Base class for registry tests with cleanup."""

    def setUp(self):
        """Clear registry before each test."""
        clear_registry()

    def tearDown(self):
        """Clear registry after each test."""
        clear_registry()


class TestRegisterSchema(TestSchemaRegistryBase):
    """Tests for register_schema function."""

    def test_register_schema_basic(self):
        """Test basic schema registration."""
        schema = SiteSchema(name='test', url_pattern=r'.*')
        register_schema(schema)
        self.assertTrue(is_registered('test'))

    def test_register_multiple_schemas(self):
        """Test registering multiple schemas."""
        schema1 = SiteSchema(name='schema1', url_pattern=r'https://site1\.com/.*')
        schema2 = SiteSchema(name='schema2', url_pattern=r'https://site2\.com/.*')
        register_schema(schema1)
        register_schema(schema2)
        self.assertEqual(schema_count(), 2)
        self.assertTrue(is_registered('schema1'))
        self.assertTrue(is_registered('schema2'))

    def test_register_duplicate_raises_error(self):
        """Test that registering duplicate name raises ValueError."""
        schema1 = SiteSchema(name='duplicate', url_pattern=r'.*')
        schema2 = SiteSchema(name='duplicate', url_pattern=r'https://other\.com/.*')
        register_schema(schema1)
        with self.assertRaises(ValueError) as context:
            register_schema(schema2)
        self.assertIn('already registered', str(context.exception))

    def test_register_with_overwrite(self):
        """Test that overwrite=True allows replacing schemas."""
        schema1 = SiteSchema(name='overwrite_test', url_pattern=r'https://old\.com/.*')
        schema2 = SiteSchema(name='overwrite_test', url_pattern=r'https://new\.com/.*')
        register_schema(schema1)
        register_schema(schema2, overwrite=True)

        retrieved = get_schema('overwrite_test')
        self.assertEqual(retrieved.url_pattern, r'https://new\.com/.*')

    def test_register_invalid_type_raises_error(self):
        """Test that registering non-SiteSchema raises TypeError."""
        with self.assertRaises(TypeError) as context:
            register_schema("not a schema")
        self.assertIn('Expected SiteSchema', str(context.exception))

    def test_register_dict_raises_error(self):
        """Test that registering a dict raises TypeError."""
        with self.assertRaises(TypeError):
            register_schema({'name': 'test', 'url_pattern': '.*'})


class TestUnregisterSchema(TestSchemaRegistryBase):
    """Tests for unregister_schema function."""

    def test_unregister_existing(self):
        """Test unregistering an existing schema."""
        schema = SiteSchema(name='to_remove', url_pattern=r'.*')
        register_schema(schema)
        self.assertTrue(is_registered('to_remove'))

        result = unregister_schema('to_remove')
        self.assertTrue(result)
        self.assertFalse(is_registered('to_remove'))

    def test_unregister_nonexistent(self):
        """Test unregistering a schema that doesn't exist."""
        result = unregister_schema('nonexistent')
        self.assertFalse(result)

    def test_unregister_and_reregister(self):
        """Test that schema can be re-registered after unregistering."""
        schema = SiteSchema(name='reregister', url_pattern=r'.*')
        register_schema(schema)
        unregister_schema('reregister')

        # Should be able to register again without overwrite
        register_schema(schema)
        self.assertTrue(is_registered('reregister'))


class TestGetSchema(TestSchemaRegistryBase):
    """Tests for get_schema function."""

    def test_get_existing_schema(self):
        """Test getting an existing schema."""
        original = SiteSchema(
            name='get_test',
            url_pattern=r'https://test\.com/.*',
            description='Test schema'
        )
        register_schema(original)

        retrieved = get_schema('get_test')
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.name, 'get_test')
        self.assertEqual(retrieved.description, 'Test schema')

    def test_get_nonexistent_schema(self):
        """Test getting a schema that doesn't exist."""
        result = get_schema('nonexistent')
        self.assertIsNone(result)

    def test_get_returns_same_instance(self):
        """Test that get_schema returns the same instance."""
        original = SiteSchema(name='instance_test', url_pattern=r'.*')
        register_schema(original)

        retrieved = get_schema('instance_test')
        self.assertIs(retrieved, original)


class TestDetectSchema(TestSchemaRegistryBase):
    """Tests for detect_schema function."""

    def test_detect_matching_schema(self):
        """Test detecting a schema that matches the URL."""
        schema = SiteSchema(
            name='springer',
            url_pattern=r'https?://link\.springer\.com/book/.*'
        )
        register_schema(schema)

        detected = detect_schema('https://link.springer.com/book/10.1007/978-3-031-41026-0')
        self.assertIsNotNone(detected)
        self.assertEqual(detected.name, 'springer')

    def test_detect_no_match(self):
        """Test that None is returned when no schema matches."""
        schema = SiteSchema(
            name='specific',
            url_pattern=r'https://specific-site\.com/.*'
        )
        register_schema(schema)

        detected = detect_schema('https://other-site.com/page')
        self.assertIsNone(detected)

    def test_detect_first_match_wins(self):
        """Test that the first matching schema is returned."""
        schema1 = SiteSchema(name='first', url_pattern=r'https://example\.com/.*')
        schema2 = SiteSchema(name='second', url_pattern=r'https://example\.com/docs/.*')

        # Register in order - first should match first
        register_schema(schema1)
        register_schema(schema2)

        detected = detect_schema('https://example.com/docs/page')
        # First registered schema that matches wins
        self.assertEqual(detected.name, 'first')

    def test_detect_with_multiple_schemas(self):
        """Test detection with multiple registered schemas."""
        schemas = [
            SiteSchema(name='arxiv', url_pattern=r'https?://arxiv\.org/.*'),
            SiteSchema(name='springer', url_pattern=r'https?://link\.springer\.com/.*'),
            SiteSchema(name='ieee', url_pattern=r'https?://ieeexplore\.ieee\.org/.*'),
        ]
        for s in schemas:
            register_schema(s)

        self.assertEqual(detect_schema('https://arxiv.org/abs/2301.07041').name, 'arxiv')
        self.assertEqual(detect_schema('https://link.springer.com/book/123').name, 'springer')
        self.assertEqual(detect_schema('https://ieeexplore.ieee.org/document/123').name, 'ieee')
        self.assertIsNone(detect_schema('https://unknown.com/'))

    def test_detect_empty_registry(self):
        """Test detection with empty registry."""
        detected = detect_schema('https://example.com/')
        self.assertIsNone(detected)


class TestListSchemas(TestSchemaRegistryBase):
    """Tests for list_schemas function."""

    def test_list_empty_registry(self):
        """Test listing schemas from empty registry."""
        names = list_schemas()
        self.assertEqual(names, [])

    def test_list_single_schema(self):
        """Test listing single schema."""
        schema = SiteSchema(name='single', url_pattern=r'.*')
        register_schema(schema)

        names = list_schemas()
        self.assertEqual(names, ['single'])

    def test_list_multiple_schemas_sorted(self):
        """Test that list_schemas returns sorted names."""
        schemas = [
            SiteSchema(name='zebra', url_pattern=r'.*'),
            SiteSchema(name='alpha', url_pattern=r'.*'),
            SiteSchema(name='middle', url_pattern=r'.*'),
        ]
        for s in schemas:
            register_schema(s)

        names = list_schemas()
        self.assertEqual(names, ['alpha', 'middle', 'zebra'])


class TestGetAllSchemas(TestSchemaRegistryBase):
    """Tests for get_all_schemas function."""

    def test_get_all_empty(self):
        """Test get_all_schemas with empty registry."""
        all_schemas = get_all_schemas()
        self.assertEqual(all_schemas, {})

    def test_get_all_returns_copy(self):
        """Test that get_all_schemas returns a copy."""
        schema = SiteSchema(name='copy_test', url_pattern=r'.*')
        register_schema(schema)

        all_schemas = get_all_schemas()
        all_schemas['new_key'] = 'should not affect registry'

        # Original registry should be unchanged
        self.assertNotIn('new_key', get_all_schemas())
        self.assertEqual(schema_count(), 1)

    def test_get_all_contains_all_schemas(self):
        """Test that get_all_schemas contains all registered schemas."""
        schemas = [
            SiteSchema(name='one', url_pattern=r'.*'),
            SiteSchema(name='two', url_pattern=r'.*'),
        ]
        for s in schemas:
            register_schema(s)

        all_schemas = get_all_schemas()
        self.assertEqual(len(all_schemas), 2)
        self.assertIn('one', all_schemas)
        self.assertIn('two', all_schemas)


class TestClearRegistry(TestSchemaRegistryBase):
    """Tests for clear_registry function."""

    def test_clear_empty_registry(self):
        """Test clearing an empty registry."""
        clear_registry()  # Should not raise
        self.assertEqual(schema_count(), 0)

    def test_clear_populated_registry(self):
        """Test clearing a populated registry."""
        for i in range(5):
            schema = SiteSchema(name=f'schema_{i}', url_pattern=r'.*')
            register_schema(schema)

        self.assertEqual(schema_count(), 5)
        clear_registry()
        self.assertEqual(schema_count(), 0)
        self.assertEqual(list_schemas(), [])


class TestSchemaDecorator(TestSchemaRegistryBase):
    """Tests for the @schema decorator."""

    def test_decorator_with_instance(self):
        """Test @schema decorator with a SiteSchema instance."""
        instance = SiteSchema(name='decorated_instance', url_pattern=r'.*')
        result = schema(instance)

        self.assertIs(result, instance)
        self.assertTrue(is_registered('decorated_instance'))

    def test_decorator_with_class(self):
        """Test @schema decorator with a SiteSchema subclass."""
        @schema
        class MySchema(SiteSchema):
            def __init__(self):
                super().__init__(
                    name='decorated_class',
                    url_pattern=r'https://mysite\.com/.*',
                    description='Decorated class schema'
                )

        self.assertTrue(is_registered('decorated_class'))
        retrieved = get_schema('decorated_class')
        self.assertEqual(retrieved.description, 'Decorated class schema')

    def test_decorator_with_invalid_type(self):
        """Test @schema decorator with invalid type."""
        with self.assertRaises(TypeError) as context:
            schema("not a schema")
        self.assertIn('expects SiteSchema', str(context.exception))

    def test_decorator_with_non_schema_class(self):
        """Test @schema decorator with non-SiteSchema class."""
        class NotASchema:
            pass

        with self.assertRaises(TypeError):
            schema(NotASchema)


class TestIsRegistered(TestSchemaRegistryBase):
    """Tests for is_registered function."""

    def test_is_registered_true(self):
        """Test is_registered returns True for registered schema."""
        schema = SiteSchema(name='registered', url_pattern=r'.*')
        register_schema(schema)
        self.assertTrue(is_registered('registered'))

    def test_is_registered_false(self):
        """Test is_registered returns False for unregistered schema."""
        self.assertFalse(is_registered('not_registered'))

    def test_is_registered_after_unregister(self):
        """Test is_registered returns False after unregistering."""
        schema = SiteSchema(name='temp', url_pattern=r'.*')
        register_schema(schema)
        unregister_schema('temp')
        self.assertFalse(is_registered('temp'))


class TestSchemaCount(TestSchemaRegistryBase):
    """Tests for schema_count function."""

    def test_count_empty(self):
        """Test count of empty registry."""
        self.assertEqual(schema_count(), 0)

    def test_count_after_registrations(self):
        """Test count after registering schemas."""
        for i in range(3):
            schema = SiteSchema(name=f'count_{i}', url_pattern=r'.*')
            register_schema(schema)
        self.assertEqual(schema_count(), 3)

    def test_count_after_unregister(self):
        """Test count after unregistering."""
        for i in range(3):
            schema = SiteSchema(name=f'uncount_{i}', url_pattern=r'.*')
            register_schema(schema)

        unregister_schema('uncount_1')
        self.assertEqual(schema_count(), 2)


if __name__ == '__main__':
    unittest.main()
