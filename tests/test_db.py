#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sqlite3
import tempfile
import unittest

from everdo.model import ListType, TagType
from tests.conftest import (
    ACTION_ACTIVE_ID,
    ACTION_DONE_ID,
    ACTION_FOCUSED_ID,
    ARCHIVED_PROJECT_ID,
    ARCHIVED_TASK_1_ID,
    ARCHIVED_TASK_2_ID,
    INBOX_1_ID,
    NOTE_1_ID,
    NOTE_2_ID,
    NOTEBOOK_ID,
    PROJECT_ID,
    SCHEDULED_ID,
    SOMEDAY_ID,
    WAITING_ID,
    create_test_db,
    open_test_db,
)


class DBTestCase(unittest.TestCase):
    """Base class that sets up a temp test database."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._db_path = create_test_db(self._tmpdir.name)
        self.db = open_test_db(self._db_path)

    def tearDown(self):
        self.db.close()
        self._tmpdir.cleanup()


class TestInbox(DBTestCase):
    def test_inbox_count(self):
        items = self.db.inbox()
        self.assertEqual(len(items), 2)

    def test_inbox_all_incomplete(self):
        for item in self.db.inbox():
            self.assertFalse(item.is_complete)


class TestProjects(DBTestCase):
    def test_active_projects(self):
        projects = self.db.active_projects()
        self.assertEqual(len(projects), 1)
        self.assertEqual(projects[0].title, "Test Project")
        self.assertEqual(projects[0].id, PROJECT_ID)

    def test_all_projects(self):
        projects = self.db.all_projects()
        self.assertEqual(
            [p.id for p in projects],
            [ARCHIVED_PROJECT_ID, PROJECT_ID],  # "Old Trip 2024" sorts before "Test Project"
        )

    def test_all_projects_filtered_archived(self):
        projects = self.db.all_projects(ListType.ARCHIVED)
        self.assertEqual([p.id for p in projects], [ARCHIVED_PROJECT_ID])
        self.assertTrue(projects[0].is_complete)

    def test_all_projects_filtered_active(self):
        projects = self.db.all_projects(ListType.ACTIVE)
        self.assertEqual([p.id for p in projects], [PROJECT_ID])


class TestNextActions(DBTestCase):
    def test_all_next_actions(self):
        actions = self.db.next_actions()
        ids = {a.id for a in actions}
        self.assertIn(ACTION_FOCUSED_ID, ids)
        self.assertIn(ACTION_ACTIVE_ID, ids)
        self.assertNotIn(ACTION_DONE_ID, ids)

    def test_next_actions_by_project(self):
        actions = self.db.next_actions(PROJECT_ID)
        ids = {a.id for a in actions}
        self.assertIn(ACTION_FOCUSED_ID, ids)
        self.assertIn(ACTION_ACTIVE_ID, ids)
        self.assertEqual(len(actions), 2)


class TestWaiting(DBTestCase):
    def test_waiting(self):
        items = self.db.waiting()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].id, WAITING_ID)


class TestScheduled(DBTestCase):
    def test_scheduled(self):
        items = self.db.scheduled()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].id, SCHEDULED_ID)


class TestSomedayMaybe(DBTestCase):
    def test_someday_maybe(self):
        items = self.db.someday_maybe()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].id, SOMEDAY_ID)


class TestFocused(DBTestCase):
    def test_focused(self):
        items = self.db.focused()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].id, ACTION_FOCUSED_ID)
        self.assertTrue(items[0].is_focused)


class TestNotebooks(DBTestCase):
    def test_notebooks(self):
        items = self.db.notebooks()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].title, "My Notebook")


class TestNotes(DBTestCase):
    def test_notes_all(self):
        items = self.db.notes()
        self.assertEqual(len(items), 2)

    def test_notes_filtered(self):
        items = self.db.notes(NOTEBOOK_ID)
        self.assertEqual(len(items), 2)
        ids = {n.id for n in items}
        self.assertIn(NOTE_1_ID, ids)
        self.assertIn(NOTE_2_ID, ids)


class TestProjectTasks(DBTestCase):
    def test_project_tasks(self):
        tasks = self.db.project_tasks(PROJECT_ID)
        self.assertEqual(len(tasks), 3)
        ids = {t.id for t in tasks}
        self.assertIn(ACTION_DONE_ID, ids)
        self.assertIn(ACTION_FOCUSED_ID, ids)
        self.assertIn(ACTION_ACTIVE_ID, ids)

    def test_project_tasks_of_archived_project(self):
        tasks = self.db.project_tasks(ARCHIVED_PROJECT_ID)
        ids = {t.id for t in tasks}
        self.assertEqual(ids, {ARCHIVED_TASK_1_ID, ARCHIVED_TASK_2_ID})


class TestProjectSummary(DBTestCase):
    def test_project_summary(self):
        summaries = self.db.project_summary()
        self.assertEqual(len(summaries), 1)
        proj, open_count, done_count = summaries[0]
        self.assertEqual(proj.id, PROJECT_ID)
        self.assertEqual(open_count, 2)
        self.assertEqual(done_count, 1)


class TestTags(DBTestCase):
    def test_all_tags(self):
        tags = self.db.tags()
        self.assertEqual(len(tags), 3)

    def test_tags_filtered_area(self):
        tags = self.db.tags(TagType.AREA)
        self.assertEqual(len(tags), 1)
        self.assertEqual(tags[0].title, "Work")

    def test_tags_filtered_contact(self):
        tags = self.db.tags(TagType.CONTACT)
        self.assertEqual(len(tags), 1)
        self.assertEqual(tags[0].title, "Alice")

    def test_tags_filtered_label(self):
        tags = self.db.tags(TagType.LABEL)
        self.assertEqual(len(tags), 1)
        self.assertEqual(tags[0].title, "urgent")


class TestDone(DBTestCase):
    def test_all_done_newest_completion_first(self):
        items = self.db.done()
        self.assertEqual(
            [i.id for i in items],
            [ARCHIVED_TASK_2_ID, ARCHIVED_TASK_1_ID, ACTION_DONE_ID],
        )

    def test_done_by_project(self):
        items = self.db.done(project_id=PROJECT_ID)
        self.assertEqual([i.id for i in items], [ACTION_DONE_ID])

    def test_done_by_unknown_project(self):
        self.assertEqual(self.db.done(project_id="ff" * 16), [])

    def test_done_limit(self):
        self.assertEqual(self.db.done(limit=0), [])

    def test_done_no_limit(self):
        items = self.db.done(limit=None)
        self.assertEqual(len(items), 3)

    def test_done_ambiguous_project_prefix(self):
        # every fixture item ID starts with "0", so the prefix is ambiguous
        self.assertEqual(self.db.done(project_id="0"), [])

    def test_done_non_hex_project_id(self):
        self.assertEqual(self.db.done(project_id="zz" * 16), [])


class TestSearch(DBTestCase):
    def test_search_case_insensitive(self):
        items = self.db.search("inbox")
        self.assertEqual(len(items), 2)

    def test_search_partial(self):
        items = self.db.search("Focused")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].id, ACTION_FOCUSED_ID)

    def test_search_excludes_completed(self):
        # "Done Task" matches the query but is completed and must not appear
        self.assertEqual(self.db.search("Done"), [])

    def test_search_include_done(self):
        items = self.db.search("Done", include_done=True)
        self.assertEqual([i.id for i in items], [ACTION_DONE_ID])


class TestFindProjects(DBTestCase):
    def test_by_title_substring(self):
        items = self.db.find_projects("Project")
        self.assertEqual([i.id for i in items], [PROJECT_ID])

    def test_by_hex_prefix(self):
        items = self.db.find_projects(PROJECT_ID[:8])
        self.assertEqual([i.id for i in items], [PROJECT_ID])

    def test_by_odd_length_hex_prefix(self):
        items = self.db.find_projects(PROJECT_ID[:3])
        self.assertEqual([i.id for i in items], [PROJECT_ID])

    def test_hex_miss_falls_back_to_title(self):
        # valid hex prefix that matches no ID and no title
        self.assertEqual(self.db.find_projects("deadbeef"), [])


class TestFindNotebooks(DBTestCase):
    def test_by_title_substring(self):
        items = self.db.find_notebooks("Notebook")
        self.assertEqual([i.id for i in items], [NOTEBOOK_ID])

    def test_by_hex_prefix(self):
        items = self.db.find_notebooks(NOTEBOOK_ID[:8])
        self.assertEqual([i.id for i in items], [NOTEBOOK_ID])

    def test_by_odd_length_hex_prefix(self):
        items = self.db.find_notebooks(NOTEBOOK_ID[:3])
        self.assertEqual([i.id for i in items], [NOTEBOOK_ID])

    def test_hex_miss_falls_back_to_title(self):
        self.assertEqual(self.db.find_notebooks("deadbeef"), [])


class TestProjectTitles(DBTestCase):
    def test_project_titles(self):
        self.assertEqual(
            self.db.project_titles(),
            {PROJECT_ID: "Test Project", ARCHIVED_PROJECT_ID: "Old Trip 2024"},
        )


class TestGetItem(DBTestCase):
    def test_full_id(self):
        item = self.db.get_item(PROJECT_ID)
        self.assertIsNotNone(item)
        self.assertEqual(item.title, "Test Project")

    def test_prefix(self):
        item = self.db.get_item("01010101")
        self.assertIsNotNone(item)
        self.assertEqual(item.id, PROJECT_ID)

    def test_not_found(self):
        item = self.db.get_item("ff" * 16)
        self.assertIsNone(item)

    def test_full_id_invalid_hex(self):
        self.assertIsNone(self.db.get_item("zz" * 16))

    def test_odd_length_prefix(self):
        item = self.db.get_item(PROJECT_ID[:7])
        self.assertIsNotNone(item)
        self.assertEqual(item.id, PROJECT_ID)

    def test_non_hex_prefix_returns_none(self):
        # used to raise ValueError via bytes.fromhex
        self.assertIsNone(self.db.get_item("not-a-hex-id"))


class TestUnknownCodes(DBTestCase):
    """Rows with type/list/tag codes from a newer Everdo version must be skipped, not crash."""

    def _insert_raw(self, sql, params):
        conn = sqlite3.connect(str(self._db_path))
        conn.execute(sql, params)
        conn.commit()
        conn.close()

    def _reopen(self):
        self.db.close()
        self.db = open_test_db(self._db_path)

    def test_unknown_item_type_is_skipped(self):
        self._insert_raw(
            "INSERT INTO item (id, title, type, list, created_on) VALUES (?, ?, ?, ?, ?)",
            (bytes.fromhex("ee" * 16), "Future Item", "x", "i", 1700000000),
        )
        self._reopen()
        ids = {i.id for i in self.db.inbox()}
        self.assertNotIn("ee" * 16, ids)
        self.assertEqual(len(ids), 2)  # the two fixture inbox items still load

    def test_unknown_tag_type_is_skipped(self):
        self._insert_raw(
            "INSERT INTO tag (id, type, title, color) VALUES (?, ?, ?, ?)",
            (bytes.fromhex("dd" * 16), "x", "Future Tag", None),
        )
        self._reopen()  # _load_tags runs at connection time and must not raise
        self.assertEqual(len(self.db.tags()), 3)


class TestTagsOnItems(DBTestCase):
    def test_project_has_area_tag(self):
        item = self.db.get_item(PROJECT_ID)
        self.assertIsNotNone(item)
        self.assertEqual(len(item.tags), 1)
        self.assertEqual(item.tags[0].title, "Work")

    def test_focused_has_label_tag(self):
        item = self.db.get_item(ACTION_FOCUSED_ID)
        self.assertIsNotNone(item)
        self.assertEqual(len(item.tags), 1)
        self.assertEqual(item.tags[0].title, "urgent")

    def test_inbox_1_has_area_tag(self):
        item = self.db.get_item(INBOX_1_ID)
        self.assertIsNotNone(item)
        self.assertEqual(len(item.tags), 1)
        self.assertEqual(item.tags[0].title, "Work")


if __name__ == "__main__":
    unittest.main()
