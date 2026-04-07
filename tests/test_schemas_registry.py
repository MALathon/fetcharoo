"""Tests for the community site schemas registry."""

import unittest

from fetcharoo.schemas import find_schema, list_schemas, SiteSchema
from fetcharoo.schemas.sites import BUILTIN_SCHEMAS


class TestSchemaRegistry(unittest.TestCase):
    """Test the schema registry."""

    def test_list_schemas_returns_all(self):
        schemas = list_schemas()
        self.assertGreaterEqual(len(schemas), 5)

    def test_all_schemas_are_site_schemas(self):
        for schema in list_schemas():
            self.assertIsInstance(schema, SiteSchema)

    def test_all_schemas_have_names(self):
        for schema in list_schemas():
            self.assertTrue(schema.name)

    def test_all_schemas_have_url_patterns(self):
        for schema in list_schemas():
            self.assertTrue(schema.url_pattern)

    def test_all_schemas_have_descriptions(self):
        for schema in list_schemas():
            self.assertTrue(schema.description)

    def test_schema_names_are_unique(self):
        names = [s.name for s in list_schemas()]
        self.assertEqual(len(names), len(set(names)))


class TestFindSchema(unittest.TestCase):
    """Test auto-detection of schemas by URL."""

    def test_find_arxiv_schema(self):
        schema = find_schema('https://arxiv.org/abs/2301.00001')
        self.assertIsNotNone(schema)
        self.assertEqual(schema.name, 'arxiv')

    def test_find_ietf_rfc_schema(self):
        schema = find_schema('https://www.rfc-editor.org/rfc/rfc9110')
        self.assertIsNotNone(schema)
        self.assertEqual(schema.name, 'ietf_rfc')

    def test_find_w3c_schema(self):
        schema = find_schema('https://www.w3.org/TR/css-flexbox-1/')
        self.assertIsNotNone(schema)
        self.assertEqual(schema.name, 'w3c')

    def test_find_federal_register_schema(self):
        schema = find_schema('https://www.federalregister.gov/documents/2024/01/01/test')
        self.assertIsNotNone(schema)
        self.assertEqual(schema.name, 'federal_register')

    def test_no_match_returns_none(self):
        schema = find_schema('https://random-unknown-site.com/page')
        self.assertIsNone(schema)


class TestBuiltinSchemas(unittest.TestCase):
    """Test individual built-in schemas."""

    def test_arxiv_schema_properties(self):
        schema = find_schema('https://arxiv.org/abs/2301.00001')
        self.assertEqual(schema.request_delay, 1.0)  # arXiv rate limits

    def test_ietf_rfc_schema_excludes_drafts(self):
        schema = find_schema('https://www.rfc-editor.org/rfc/rfc9110')
        self.assertIn('*draft*', schema.exclude_patterns)
        self.assertEqual(schema.sort_by, 'numeric')

    def test_sec_edgar_schema_depth(self):
        schema = find_schema('https://www.sec.gov/Archives/edgar/data/12345')
        self.assertIsNotNone(schema)
        self.assertEqual(schema.recommended_depth, 2)

    def test_schema_get_filter_config(self):
        schema = find_schema('https://www.rfc-editor.org/rfc/rfc9110')
        config = schema.get_filter_config()
        self.assertIsNotNone(config)
        self.assertTrue(config.filename_include or config.filename_exclude)


if __name__ == '__main__':
    unittest.main()
