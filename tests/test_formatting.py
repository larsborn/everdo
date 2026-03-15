#!/usr/bin/env python
# -*- coding: utf-8 -*-
import io
import sys
import unittest
from datetime import datetime, timezone

from everdo.formatting import (
    _truncate,
    format_date,
    format_energy,
    format_tags,
    format_time,
    print_item_detail,
    print_items,
)
from everdo.model import Item, ItemType, ListType, Tag, TagType


class TestFormatDate(unittest.TestCase):
    def test_none(self):
        self.assertEqual(format_date(None), "")

    def test_valid(self):
        dt = datetime(2024, 3, 15, tzinfo=timezone.utc)
        self.assertEqual(format_date(dt), "2024-03-15")


class TestFormatTags(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(format_tags([]), "")

    def test_single(self):
        t = Tag(id="aa", title="Work", type=TagType.AREA)
        self.assertEqual(format_tags([t]), "@Work")

    def test_multiple(self):
        tags = [
            Tag(id="aa", title="Work", type=TagType.AREA),
            Tag(id="bb", title="urgent", type=TagType.LABEL),
        ]
        self.assertEqual(format_tags(tags), "@Work @urgent")


class TestFormatEnergy(unittest.TestCase):
    def test_none(self):
        self.assertEqual(format_energy(None), "")

    def test_low(self):
        self.assertEqual(format_energy(1), "low")

    def test_medium(self):
        self.assertEqual(format_energy(2), "medium")

    def test_high(self):
        self.assertEqual(format_energy(3), "high")


class TestFormatTime(unittest.TestCase):
    def test_none(self):
        self.assertEqual(format_time(None), "")

    def test_minutes(self):
        self.assertEqual(format_time(30), "30m")

    def test_hours(self):
        self.assertEqual(format_time(120), "2h")

    def test_hours_minutes(self):
        self.assertEqual(format_time(90), "1h30m")


class TestTruncate(unittest.TestCase):
    def test_short(self):
        self.assertEqual(_truncate("hi", 10), "hi")

    def test_exact(self):
        self.assertEqual(_truncate("hello", 5), "hello")

    def test_truncated(self):
        self.assertEqual(_truncate("hello world", 8), "hello...")

    def test_very_short_width(self):
        self.assertEqual(_truncate("hello", 2), "he")


class TestPrintItems(unittest.TestCase):
    def test_empty(self):
        captured = io.StringIO()
        sys.stdout = captured
        try:
            print_items([], "Test")
        finally:
            sys.stdout = sys.__stdout__
        out = captured.getvalue()
        self.assertIn("Test", out)
        self.assertIn("(none)", out)

    def test_with_items(self):
        items = [
            Item(
                id="aabbccdd11223344",
                title="My Task",
                type=ItemType.ACTION,
                list_type=ListType.ACTIVE,
                is_focused=True,
                tags=[Tag(id="tt", title="Work", type=TagType.AREA)],
            ),
        ]
        captured = io.StringIO()
        sys.stdout = captured
        try:
            print_items(items, "Actions")
        finally:
            sys.stdout = sys.__stdout__
        out = captured.getvalue()
        self.assertIn("aabbccdd", out)
        self.assertIn("My Task", out)
        self.assertIn("*", out)
        self.assertIn("@Work", out)


class TestPrintItemDetail(unittest.TestCase):
    def test_full_detail(self):
        item = Item(
            id="aabb" * 8,
            title="Detail Item",
            type=ItemType.ACTION,
            list_type=ListType.ACTIVE,
            is_focused=True,
            energy=2,
            time=45,
            note="A note body",
            tags=[Tag(id="tt", title="urgent", type=TagType.LABEL)],
        )
        captured = io.StringIO()
        sys.stdout = captured
        try:
            print_item_detail(item)
        finally:
            sys.stdout = sys.__stdout__
        out = captured.getvalue()
        self.assertIn("Detail Item", out)
        self.assertIn("medium", out)
        self.assertIn("45m", out)
        self.assertIn("@urgent", out)
        self.assertIn("A note body", out)
        self.assertIn("yes", out)  # focused


if __name__ == "__main__":
    unittest.main()
