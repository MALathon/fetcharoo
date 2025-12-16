"""
Tests for the SiteSchema base dataclass.
"""

import unittest
from fetcharoo.schemas import SiteSchema
from fetcharoo.filtering import FilterConfig


class TestSiteSchemaBasic(unittest.TestCase):
    """Basic tests for SiteSchema instantiation and attributes."""

    def test_create_minimal_schema(self):
        """Test creating a schema with only required fields."""
        schema = SiteSchema(
            name='test_schema',
            url_pattern=r'https://example\.com/.*'
        )
        self.assertEqual(schema.name, 'test_schema')
        self.assertEqual(schema.url_pattern, r'https://example\.com/.*')
        self.assertIsNone(schema.description)
        self.assertEqual(schema.include_patterns, [])
        self.assertEqual(schema.exclude_patterns, [])
        self.assertIsNone(schema.sort_by)
        self.assertEqual(schema.recommended_depth, 1)
        self.assertEqual(schema.request_delay, 0.5)
        self.assertEqual(schema.version, "1.0.0")

    def test_create_full_schema(self):
        """Test creating a schema with all fields."""
        def custom_sort(url):
            return url

        schema = SiteSchema(
            name='full_schema',
            url_pattern=r'https://full\.example\.com/.*',
            description='A fully configured schema',
            include_patterns=['*.pdf', 'report*.pdf'],
            exclude_patterns=['*draft*'],
            url_include_patterns=['*/docs/*'],
            url_exclude_patterns=['*/temp/*'],
            sort_by='numeric',
            sort_key=custom_sort,
            default_output_name='output.pdf',
            recommended_depth=2,
            request_delay=1.5,
            test_url='https://full.example.com/test',
            expected_min_pdfs=5,
            version='2.0.0'
        )

        self.assertEqual(schema.name, 'full_schema')
        self.assertEqual(schema.description, 'A fully configured schema')
        self.assertEqual(schema.include_patterns, ['*.pdf', 'report*.pdf'])
        self.assertEqual(schema.exclude_patterns, ['*draft*'])
        self.assertEqual(schema.sort_by, 'numeric')
        self.assertEqual(schema.sort_key, custom_sort)
        self.assertEqual(schema.default_output_name, 'output.pdf')
        self.assertEqual(schema.recommended_depth, 2)
        self.assertEqual(schema.request_delay, 1.5)
        self.assertEqual(schema.test_url, 'https://full.example.com/test')
        self.assertEqual(schema.expected_min_pdfs, 5)
        self.assertEqual(schema.version, '2.0.0')


class TestSiteSchemaMatches(unittest.TestCase):
    """Tests for the matches() method."""

    def test_matches_simple_pattern(self):
        """Test matching a simple URL pattern."""
        schema = SiteSchema(
            name='test',
            url_pattern=r'https://example\.com/.*'
        )
        self.assertTrue(schema.matches('https://example.com/'))
        self.assertTrue(schema.matches('https://example.com/page'))
        self.assertTrue(schema.matches('https://example.com/docs/file.pdf'))
        self.assertFalse(schema.matches('https://other.com/'))
        self.assertFalse(schema.matches('http://example.com/'))  # http vs https

    def test_matches_complex_pattern(self):
        """Test matching a complex URL pattern."""
        schema = SiteSchema(
            name='springer',
            url_pattern=r'https?://link\.springer\.com/book/10\.\d+/.*'
        )
        self.assertTrue(schema.matches('https://link.springer.com/book/10.1007/978-3-031-41026-0'))
        self.assertTrue(schema.matches('http://link.springer.com/book/10.1234/some-book'))
        self.assertFalse(schema.matches('https://link.springer.com/article/10.1007/something'))
        self.assertFalse(schema.matches('https://springer.com/book/10.1007/something'))

    def test_matches_with_capture_groups(self):
        """Test that patterns with capture groups work."""
        schema = SiteSchema(
            name='arxiv',
            url_pattern=r'https?://arxiv\.org/(abs|pdf)/(\d+\.\d+)'
        )
        self.assertTrue(schema.matches('https://arxiv.org/abs/2301.07041'))
        self.assertTrue(schema.matches('https://arxiv.org/pdf/2301.07041'))
        self.assertFalse(schema.matches('https://arxiv.org/list/2301.07041'))

    def test_matches_empty_pattern(self):
        """Test behavior with empty URL pattern."""
        schema = SiteSchema(name='empty', url_pattern='')
        # Empty pattern is not compiled, so matches() returns False for all
        self.assertFalse(schema.matches(''))
        self.assertFalse(schema.matches('https://example.com'))

    def test_matches_catch_all_pattern(self):
        """Test a catch-all pattern."""
        schema = SiteSchema(name='generic', url_pattern=r'.*')
        self.assertTrue(schema.matches('https://example.com'))
        self.assertTrue(schema.matches('anything'))
        self.assertTrue(schema.matches(''))


class TestSiteSchemaValidation(unittest.TestCase):
    """Tests for schema validation during initialization."""

    def test_invalid_regex_raises_error(self):
        """Test that invalid regex pattern raises ValueError."""
        with self.assertRaises(ValueError) as context:
            SiteSchema(name='bad', url_pattern=r'[invalid')
        self.assertIn('Invalid url_pattern regex', str(context.exception))

    def test_invalid_sort_by_raises_error(self):
        """Test that invalid sort_by value raises ValueError."""
        with self.assertRaises(ValueError) as context:
            SiteSchema(
                name='bad_sort',
                url_pattern=r'.*',
                sort_by='invalid_sort_option'
            )
        self.assertIn('sort_by must be one of', str(context.exception))

    def test_valid_sort_by_options(self):
        """Test that all valid sort_by options are accepted."""
        valid_options = [None, 'none', 'numeric', 'alpha', 'alpha_desc']
        for option in valid_options:
            schema = SiteSchema(
                name=f'sort_{option}',
                url_pattern=r'.*',
                sort_by=option
            )
            self.assertEqual(schema.sort_by, option)


class TestSiteSchemaGetFilterConfig(unittest.TestCase):
    """Tests for the get_filter_config() method."""

    def test_no_filters_returns_none(self):
        """Test that schema with no filters returns None."""
        schema = SiteSchema(name='no_filters', url_pattern=r'.*')
        self.assertIsNone(schema.get_filter_config())

    def test_include_patterns_only(self):
        """Test filter config with only include patterns."""
        schema = SiteSchema(
            name='include_only',
            url_pattern=r'.*',
            include_patterns=['*.pdf', 'report*.pdf']
        )
        config = schema.get_filter_config()
        self.assertIsInstance(config, FilterConfig)
        self.assertEqual(config.filename_include, ['*.pdf', 'report*.pdf'])
        self.assertEqual(config.filename_exclude, [])

    def test_exclude_patterns_only(self):
        """Test filter config with only exclude patterns."""
        schema = SiteSchema(
            name='exclude_only',
            url_pattern=r'.*',
            exclude_patterns=['*draft*', '*temp*']
        )
        config = schema.get_filter_config()
        self.assertIsInstance(config, FilterConfig)
        self.assertEqual(config.filename_include, [])
        self.assertEqual(config.filename_exclude, ['*draft*', '*temp*'])

    def test_url_patterns(self):
        """Test filter config with URL patterns."""
        schema = SiteSchema(
            name='url_filters',
            url_pattern=r'.*',
            url_include_patterns=['*/docs/*'],
            url_exclude_patterns=['*/temp/*']
        )
        config = schema.get_filter_config()
        self.assertIsInstance(config, FilterConfig)
        self.assertEqual(config.url_include, ['*/docs/*'])
        self.assertEqual(config.url_exclude, ['*/temp/*'])

    def test_combined_filters(self):
        """Test filter config with all filter types."""
        schema = SiteSchema(
            name='combined',
            url_pattern=r'.*',
            include_patterns=['*.pdf'],
            exclude_patterns=['*draft*'],
            url_include_patterns=['*/reports/*'],
            url_exclude_patterns=['*/archive/*']
        )
        config = schema.get_filter_config()
        self.assertEqual(config.filename_include, ['*.pdf'])
        self.assertEqual(config.filename_exclude, ['*draft*'])
        self.assertEqual(config.url_include, ['*/reports/*'])
        self.assertEqual(config.url_exclude, ['*/archive/*'])

    def test_filter_config_is_copy(self):
        """Test that filter config returns copies of lists."""
        schema = SiteSchema(
            name='copy_test',
            url_pattern=r'.*',
            include_patterns=['*.pdf']
        )
        config1 = schema.get_filter_config()
        config2 = schema.get_filter_config()

        # Modify one config
        config1.filename_include.append('new.pdf')

        # Other config should be unaffected
        self.assertEqual(config2.filename_include, ['*.pdf'])
        # Original schema should be unaffected
        self.assertEqual(schema.include_patterns, ['*.pdf'])


class TestSiteSchemaGetSortKey(unittest.TestCase):
    """Tests for the get_sort_key() method."""

    def test_no_sort_returns_none(self):
        """Test that no sort config returns None."""
        schema = SiteSchema(name='no_sort', url_pattern=r'.*')
        self.assertIsNone(schema.get_sort_key())

    def test_sort_by_none_returns_none(self):
        """Test that sort_by='none' returns None."""
        schema = SiteSchema(name='sort_none', url_pattern=r'.*', sort_by='none')
        self.assertIsNone(schema.get_sort_key())

    def test_sort_by_without_custom_key_returns_none(self):
        """Test that sort_by without custom key returns None (handled by caller)."""
        schema = SiteSchema(name='sort_numeric', url_pattern=r'.*', sort_by='numeric')
        # The actual sort key implementation is in fetcharoo.py
        # Schema just specifies the strategy
        self.assertIsNone(schema.get_sort_key())

    def test_custom_sort_key_returned(self):
        """Test that custom sort_key is returned."""
        def my_sort_key(url):
            return len(url)

        schema = SiteSchema(
            name='custom_sort',
            url_pattern=r'.*',
            sort_key=my_sort_key
        )
        self.assertEqual(schema.get_sort_key(), my_sort_key)

    def test_custom_sort_key_overrides_sort_by(self):
        """Test that custom sort_key takes precedence over sort_by."""
        def custom_key(url):
            return url.lower()

        schema = SiteSchema(
            name='override',
            url_pattern=r'.*',
            sort_by='numeric',  # This would normally use numeric sorting
            sort_key=custom_key  # But custom key takes precedence
        )
        self.assertEqual(schema.get_sort_key(), custom_key)


class TestSiteSchemaStr(unittest.TestCase):
    """Tests for string representation."""

    def test_str_with_description(self):
        """Test __str__ with description."""
        schema = SiteSchema(
            name='my_schema',
            url_pattern=r'.*',
            description='A useful schema'
        )
        self.assertEqual(str(schema), 'my_schema: A useful schema')

    def test_str_without_description(self):
        """Test __str__ without description."""
        schema = SiteSchema(name='my_schema', url_pattern=r'.*')
        self.assertEqual(str(schema), 'my_schema: No description')


class TestSiteSchemaEquality(unittest.TestCase):
    """Tests for schema equality comparison."""

    def test_equal_schemas(self):
        """Test that identical schemas are equal."""
        schema1 = SiteSchema(name='test', url_pattern=r'.*', sort_by='numeric')
        schema2 = SiteSchema(name='test', url_pattern=r'.*', sort_by='numeric')
        self.assertEqual(schema1, schema2)

    def test_different_schemas(self):
        """Test that different schemas are not equal."""
        schema1 = SiteSchema(name='test1', url_pattern=r'.*')
        schema2 = SiteSchema(name='test2', url_pattern=r'.*')
        self.assertNotEqual(schema1, schema2)


if __name__ == '__main__':
    unittest.main()
