"""Tests for MCP source monitoring and snapshot diffing."""

import json
import os
import tempfile
import unittest

from fetcharoo.mcp_monitor import (
    SnapshotStore,
    SnapshotDiff,
    SnapshotRecord,
    snapshot_data,
    _extract_nested,
    _hash_json,
)


class TestHelpers(unittest.TestCase):

    def test_extract_nested_simple(self):
        self.assertEqual(_extract_nested({"a": 1}, "a"), 1)

    def test_extract_nested_deep(self):
        data = {"a": {"b": {"c": 42}}}
        self.assertEqual(_extract_nested(data, "a.b.c"), 42)

    def test_extract_nested_missing(self):
        self.assertIsNone(_extract_nested({"a": 1}, "b"))

    def test_extract_nested_list_index(self):
        data = {"items": [{"id": "first"}, {"id": "second"}]}
        self.assertEqual(_extract_nested(data, "items.0.id"), "first")
        self.assertEqual(_extract_nested(data, "items.1.id"), "second")

    def test_extract_nested_none_safe(self):
        self.assertIsNone(_extract_nested(None, "a.b"))

    def test_hash_json_deterministic(self):
        h1 = _hash_json({"a": 1, "b": 2})
        h2 = _hash_json({"b": 2, "a": 1})  # different order, same content
        self.assertEqual(h1, h2)

    def test_hash_json_different(self):
        h1 = _hash_json({"a": 1})
        h2 = _hash_json({"a": 2})
        self.assertNotEqual(h1, h2)


class TestSnapshotStore(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mktemp(suffix='.db')
        self.store = SnapshotStore(db_path=self.tmp)

    def tearDown(self):
        self.store.close()
        if os.path.exists(self.tmp):
            os.unlink(self.tmp)

    def test_empty_store(self):
        sources = self.store.list_sources()
        self.assertEqual(len(sources), 0)

    def test_first_snapshot_all_new(self):
        records = [
            {"id": "NCT001", "title": "Trial A", "status": "RECRUITING"},
            {"id": "NCT002", "title": "Trial B", "status": "ACTIVE"},
        ]
        diff = self.store.take_snapshot("trials:diabetes", records, "id")

        self.assertEqual(len(diff.new), 2)
        self.assertEqual(len(diff.unchanged), 0)
        self.assertEqual(len(diff.removed), 0)
        self.assertTrue(diff.has_changes)

    def test_second_snapshot_unchanged(self):
        records = [{"id": "NCT001", "title": "Trial A"}]
        self.store.take_snapshot("test", records, "id")

        diff = self.store.take_snapshot("test", records, "id")
        self.assertEqual(len(diff.new), 0)
        self.assertEqual(len(diff.unchanged), 1)
        self.assertEqual(len(diff.removed), 0)
        self.assertFalse(diff.has_changes)

    def test_snapshot_detects_new(self):
        self.store.take_snapshot("test", [{"id": "A"}], "id")
        diff = self.store.take_snapshot("test", [{"id": "A"}, {"id": "B"}], "id")

        self.assertEqual(len(diff.new), 1)
        self.assertEqual(diff.new[0].record_id, "B")
        self.assertEqual(len(diff.unchanged), 1)

    def test_snapshot_detects_removed(self):
        self.store.take_snapshot("test", [{"id": "A"}, {"id": "B"}], "id")
        diff = self.store.take_snapshot("test", [{"id": "A"}], "id")

        self.assertEqual(len(diff.removed), 1)
        self.assertEqual(diff.removed[0].record_id, "B")

    def test_snapshot_detects_changed(self):
        self.store.take_snapshot("test", [{"id": "A", "val": 1}], "id")
        diff = self.store.take_snapshot("test", [{"id": "A", "val": 2}], "id")

        self.assertEqual(len(diff.changed), 1)
        self.assertEqual(diff.changed[0].record_id, "A")

    def test_snapshot_mixed_changes(self):
        self.store.take_snapshot("test", [
            {"id": "keep", "v": 1},
            {"id": "change", "v": 1},
            {"id": "remove", "v": 1},
        ], "id")

        diff = self.store.take_snapshot("test", [
            {"id": "keep", "v": 1},     # unchanged
            {"id": "change", "v": 2},    # changed
            {"id": "added", "v": 1},     # new
        ], "id")

        self.assertEqual(len(diff.unchanged), 1)
        self.assertEqual(len(diff.changed), 1)
        self.assertEqual(len(diff.new), 1)
        self.assertEqual(len(diff.removed), 1)

    def test_nested_record_id(self):
        records = [
            {"protocol": {"id_module": {"nctId": "NCT001"}}, "title": "A"},
            {"protocol": {"id_module": {"nctId": "NCT002"}}, "title": "B"},
        ]
        diff = self.store.take_snapshot("trials", records, "protocol.id_module.nctId")

        self.assertEqual(len(diff.new), 2)
        ids = {r.record_id for r in diff.new}
        self.assertEqual(ids, {"NCT001", "NCT002"})

    def test_get_current_records(self):
        records = [{"id": "A", "data": 1}, {"id": "B", "data": 2}]
        self.store.take_snapshot("test", records, "id")

        current = self.store.get_current_records("test")
        self.assertEqual(len(current), 2)

    def test_get_record(self):
        self.store.take_snapshot("test", [{"id": "A", "val": 42}], "id")
        rec = self.store.get_record("test", "A")
        self.assertIsNotNone(rec)
        self.assertEqual(rec['data']['val'], 42)

    def test_get_record_not_found(self):
        rec = self.store.get_record("test", "nonexistent")
        self.assertIsNone(rec)

    def test_snapshot_history(self):
        self.store.take_snapshot("test", [{"id": "A"}], "id")
        self.store.take_snapshot("test", [{"id": "A"}, {"id": "B"}], "id")

        history = self.store.get_snapshot_history("test")
        self.assertEqual(len(history), 2)

    def test_list_sources(self):
        self.store.take_snapshot("source_a", [{"id": "1"}], "id")
        self.store.take_snapshot("source_b", [{"id": "2"}, {"id": "3"}], "id")

        sources = self.store.list_sources()
        self.assertEqual(len(sources), 2)

    def test_search_records(self):
        self.store.take_snapshot("trials", [
            {"id": "NCT001", "condition": "diabetes"},
            {"id": "NCT002", "condition": "cancer"},
        ], "id")

        results = self.store.search_records("diabetes")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['record_id'], "NCT001")

    def test_export_json(self):
        self.store.take_snapshot("test", [{"id": "A"}], "id")
        exported = self.store.export_json("test")
        data = json.loads(exported)
        self.assertEqual(len(data), 1)

    def test_summary_string(self):
        diff = SnapshotDiff(
            source_key="test",
            new=[SnapshotRecord("1", "h1")],
            removed=[SnapshotRecord("2", "h2")],
        )
        self.assertIn("new=1", diff.summary)
        self.assertIn("removed=1", diff.summary)


class TestSnapshotData(unittest.TestCase):
    """Test the synchronous snapshot_data convenience function."""

    def setUp(self):
        self.tmp = tempfile.mktemp(suffix='.db')
        self.store = SnapshotStore(db_path=self.tmp)

    def tearDown(self):
        self.store.close()
        if os.path.exists(self.tmp):
            os.unlink(self.tmp)

    def test_snapshot_data_basic(self):
        records = [{"id": "1", "name": "alpha"}, {"id": "2", "name": "beta"}]
        diff = snapshot_data(self.store, "test", records, "id")
        self.assertEqual(len(diff.new), 2)
        self.assertTrue(diff.has_changes)

    def test_snapshot_data_idempotent(self):
        records = [{"id": "1", "name": "alpha"}]
        snapshot_data(self.store, "test", records, "id")
        diff = snapshot_data(self.store, "test", records, "id")
        self.assertFalse(diff.has_changes)


class TestToolCache(unittest.TestCase):
    """Test the MCP proxy tool cache."""

    def setUp(self):
        self.tmp = tempfile.mktemp(suffix='.db')
        from fetcharoo.mcp_proxy import ToolCache
        self.cache = ToolCache(db_path=self.tmp)

    def tearDown(self):
        self.cache.close()
        if os.path.exists(self.tmp):
            os.unlink(self.tmp)

    def test_cache_miss(self):
        result = self.cache.get("tool", {"q": "test"})
        self.assertIsNone(result)

    def test_cache_put_and_get(self):
        self.cache.put("tool", {"q": "test"}, "result text")
        result = self.cache.get("tool", {"q": "test"}, ttl=3600)
        self.assertEqual(result, "result text")

    def test_cache_ttl_zero_always_miss(self):
        self.cache.put("tool", {"q": "test"}, "result text")
        result = self.cache.get("tool", {"q": "test"}, ttl=0)
        self.assertIsNone(result)

    def test_cache_detects_change(self):
        self.cache.put("tool", {}, "version 1")
        changed = self.cache.put("tool", {}, "version 2")
        self.assertTrue(changed)

    def test_cache_no_change(self):
        self.cache.put("tool", {}, "same")
        changed = self.cache.put("tool", {}, "same")
        self.assertFalse(changed)

    def test_cache_invalidate(self):
        self.cache.put("tool_a", {}, "a")
        self.cache.put("tool_b", {}, "b")
        count = self.cache.invalidate("tool_a")
        self.assertEqual(count, 1)
        self.assertIsNone(self.cache.get("tool_a", {}, ttl=3600))
        self.assertIsNotNone(self.cache.get("tool_b", {}, ttl=3600))

    def test_cache_invalidate_all(self):
        self.cache.put("tool_a", {}, "a")
        self.cache.put("tool_b", {}, "b")
        count = self.cache.invalidate()
        self.assertEqual(count, 2)

    def test_cache_history(self):
        self.cache.put("tool", {}, "v1")
        self.cache.put("tool", {}, "v2")
        history = self.cache.get_history()
        self.assertEqual(len(history), 2)

    def test_get_all_entries(self):
        self.cache.put("tool_a", {"x": 1}, "a")
        self.cache.put("tool_b", {"y": 2}, "b")
        entries = self.cache.get_all_entries()
        self.assertEqual(len(entries), 2)

    def test_get_all_entries_filtered(self):
        self.cache.put("tool_a", {}, "a")
        self.cache.put("tool_b", {}, "b")
        entries = self.cache.get_all_entries("tool_a")
        self.assertEqual(len(entries), 1)


if __name__ == '__main__':
    unittest.main()
