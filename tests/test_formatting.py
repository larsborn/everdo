#!/usr/bin/env python
# -*- coding: utf-8 -*-
import io
import sys
import unittest
from datetime import datetime, timezone

from everdo.formatting import (
    _truncate,
    dedupe_titles,
    format_date,
    format_energy,
    format_tags,
    format_time,
    print_item_detail,
    print_items,
    print_titles,
)
from everdo.model import Item, ItemType, ListType, Tag, TagType


def _item(
    title: str,
    item_id: str = "ab" * 16,
    parent_id: str | None = None,
    completed: bool = False,
) -> Item:
    return Item(
        id=item_id,
        title=title,
        type=ItemType.ACTION,
        list_type=ListType.ACTIVE,
        parent_id=parent_id,
        completed_on=datetime(2024, 1, 1, tzinfo=timezone.utc) if completed else None,
    )


class TestDedupeTitles(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(dedupe_titles([]), [])

    def test_case_insensitive_dedupe_keeps_first_spelling(self):
        items = [_item("Pack Tent"), _item("pack tent"), _item("PACK TENT")]
        self.assertEqual(dedupe_titles(items), [("Pack Tent", False, [])])

    def test_strips_whitespace(self):
        items = [_item("  Sunscreen "), _item("Sunscreen")]
        self.assertEqual(dedupe_titles(items), [("Sunscreen", False, [])])

    def test_newlines_and_duplicate_spaces_collapsed(self):
        items = [_item("Pack\nthe   big\t\ttent"), _item("Pack the big tent")]
        self.assertEqual(dedupe_titles(items), [("Pack the big tent", False, [])])

    def test_sorted_alphabetically_case_insensitive(self):
        items = [_item("zelt"), _item("Visa"), _item("sunscreen")]
        titles = [t for t, _, _ in dedupe_titles(items)]
        self.assertEqual(titles, ["sunscreen", "Visa", "zelt"])

    def test_duplicate_across_projects_aggregates_sources(self):
        trip_2024, trip_2025 = "11" * 16, "22" * 16
        project_names = {trip_2024: "Trip 2024", trip_2025: "Trip 2025"}
        items = [
            _item("Pack Tent", parent_id=trip_2024),
            _item("pack tent", parent_id=trip_2025),
            _item("Buy Visa", parent_id=trip_2025),
            _item("No Project Task"),
        ]
        self.assertEqual(
            dedupe_titles(items, project_names),
            [
                ("Buy Visa", False, ["Trip 2025"]),
                ("No Project Task", False, []),
                ("Pack Tent", False, ["Trip 2024", "Trip 2025"]),
            ],
        )

    def test_unknown_parent_id_gives_no_source(self):
        items = [_item("Task", parent_id="99" * 16)]
        self.assertEqual(dedupe_titles(items, {"11" * 16: "Trip"}), [("Task", False, [])])

    def test_done_only_when_all_occurrences_completed(self):
        all_done = [_item("Pack Tent", completed=True), _item("pack tent", completed=True)]
        self.assertEqual(dedupe_titles(all_done), [("Pack Tent", True, [])])

    def test_one_open_occurrence_means_not_done(self):
        mixed = [_item("Pack Tent", completed=True), _item("pack tent")]
        self.assertEqual(dedupe_titles(mixed), [("Pack Tent", False, [])])


class TestPrintTitles(unittest.TestCase):
    def _capture(self, items, project_names=None):
        captured = io.StringIO()
        sys.stdout = captured
        try:
            print_titles(items, project_names)
        finally:
            sys.stdout = sys.__stdout__
        return captured.getvalue()

    def test_bare_without_project_names(self):
        out = self._capture([_item("Pack Tent"), _item("Buy Visa")])
        self.assertEqual(out.splitlines(), ["Buy Visa", "Pack Tent"])

    def test_table_layout_with_project_names(self):
        trip = "11" * 16
        out = self._capture([_item("Pack Tent", parent_id=trip)], {trip: "Trip 2025"})
        lines = out.splitlines()
        self.assertEqual(lines[0], "")
        # no "Done" header — the mark column is blank; Task starts at column 3
        self.assertTrue(lines[1].startswith("   Task"))
        self.assertTrue(lines[1].endswith("Project(s)"))
        self.assertEqual(set(lines[2]), {"-"})
        self.assertTrue(lines[3].startswith("   Pack Tent"))
        self.assertTrue(lines[3].endswith("Trip 2025"))

    def test_done_mark_in_first_column(self):
        trip = "11" * 16
        out = self._capture([_item("Pack Tent", parent_id=trip, completed=True)], {trip: "Trip"})
        row = out.splitlines()[3]
        self.assertTrue(row.startswith("✓  Pack Tent"))

    def test_empty_table_prints_none(self):
        out = self._capture([], {"11" * 16: "Trip"})
        self.assertIn("(none)", out)


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

    def test_multiline_title_stays_on_one_row(self):
        items = [
            Item(
                id="aabbccdd11223344",
                title="Buy\nnew   shirt\nfor trip",
                type=ItemType.ACTION,
                list_type=ListType.ACTIVE,
            ),
        ]
        captured = io.StringIO()
        sys.stdout = captured
        try:
            print_items(items, "Search")
        finally:
            sys.stdout = sys.__stdout__
        out = captured.getvalue()
        self.assertIn("Buy new shirt for trip", out)
        # header, dashes, exactly one data row (plus section title block)
        data_rows = [line for line in out.splitlines() if line.startswith("aabbccdd")]
        self.assertEqual(len(data_rows), 1)


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
