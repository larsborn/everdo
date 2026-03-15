#!/usr/bin/env python
# -*- coding: utf-8 -*-
import unittest
from datetime import datetime, timezone

from everdo.model import Energy, Item, ItemType, ListType, TagType, _ts_to_datetime


class TestEnumValues(unittest.TestCase):
    def test_item_types(self):
        self.assertEqual(ItemType.ACTION.value, "a")
        self.assertEqual(ItemType.PROJECT.value, "p")
        self.assertEqual(ItemType.NOTEBOOK.value, "l")
        self.assertEqual(ItemType.NOTE.value, "n")

    def test_item_lists(self):
        self.assertEqual(ListType.INBOX.value, "i")
        self.assertEqual(ListType.ACTIVE.value, "a")
        self.assertEqual(ListType.SCHEDULED.value, "s")
        self.assertEqual(ListType.WAITING.value, "w")
        self.assertEqual(ListType.SOMEDAY.value, "m")
        self.assertEqual(ListType.DELETED.value, "d")
        self.assertEqual(ListType.ARCHIVED.value, "r")

    def test_tag_types(self):
        self.assertEqual(TagType.AREA.value, "a")
        self.assertEqual(TagType.CONTACT.value, "c")
        self.assertEqual(TagType.LABEL.value, "l")

    def test_energy_levels(self):
        self.assertEqual(Energy.LOW, 1)
        self.assertEqual(Energy.MEDIUM, 2)
        self.assertEqual(Energy.HIGH, 3)


class TestItem(unittest.TestCase):
    def test_is_complete_false(self):
        item = Item(
            id="aabb", title="t", type=ItemType.ACTION, list_type=ListType.ACTIVE
        )
        self.assertFalse(item.is_complete)

    def test_is_complete_true(self):
        item = Item(
            id="aabb",
            title="t",
            type=ItemType.ACTION,
            list_type=ListType.ACTIVE,
            completed_on=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        self.assertTrue(item.is_complete)

    def test_short_id(self):
        item = Item(
            id="aabbccdd11223344",
            title="t",
            type=ItemType.ACTION,
            list_type=ListType.ACTIVE,
        )
        self.assertEqual(item.short_id, "aabbccdd")

    def test_is_recurring_true(self):
        item = Item(
            id="ab",
            title="t",
            type=ItemType.ACTION,
            list_type=ListType.ACTIVE,
            schedule="weekly",
        )
        self.assertTrue(item.is_recurring)

    def test_is_recurring_false_none(self):
        item = Item(id="ab", title="t", type=ItemType.ACTION, list_type=ListType.ACTIVE)
        self.assertFalse(item.is_recurring)

    def test_is_recurring_false_empty(self):
        item = Item(
            id="ab",
            title="t",
            type=ItemType.ACTION,
            list_type=ListType.ACTIVE,
            schedule="",
        )
        self.assertFalse(item.is_recurring)

    def test_has_parent_true(self):
        item = Item(
            id="ab",
            title="t",
            type=ItemType.ACTION,
            list_type=ListType.ACTIVE,
            parent_id="cc",
        )
        self.assertTrue(item.has_parent)

    def test_has_parent_false(self):
        item = Item(id="ab", title="t", type=ItemType.ACTION, list_type=ListType.ACTIVE)
        self.assertFalse(item.has_parent)


class TestTsToDatetime(unittest.TestCase):
    def test_none(self):
        self.assertIsNone(_ts_to_datetime(None))

    def test_known_timestamp(self):
        # Everdo stores timestamps as seconds since epoch
        result = _ts_to_datetime(1700000000)
        self.assertEqual(
            result, datetime(2023, 11, 14, 22, 13, 20, tzinfo=timezone.utc)
        )

    def test_zero(self):
        result = _ts_to_datetime(0)
        self.assertEqual(result, datetime(1970, 1, 1, tzinfo=timezone.utc))

    def test_recent_timestamp_not_1970(self):
        # A typical 2025 timestamp must not produce a 1970 date
        result = _ts_to_datetime(1742000000)
        self.assertGreater(result.year, 2020)


if __name__ == "__main__":
    unittest.main()
