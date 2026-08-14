#!/usr/bin/env python
# -*- coding: utf-8 -*-
import io
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from everdo.api import CreatedInboxItem, EverdoAPIError
from everdo.main import main
from tests.conftest import ACTION_ACTIVE_ID, PROJECT_ID, create_test_db


class CLITestCase(unittest.TestCase):
    """Runs main() against the fixture database, capturing output and exit code."""

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls._db_path = str(create_test_db(cls._tmpdir.name))

    @classmethod
    def tearDownClass(cls):
        cls._tmpdir.cleanup()

    def run_cli(self, *argv, db=True):
        out, err = io.StringIO(), io.StringIO()
        code = 0
        args = ["--db", self._db_path, *argv] if db else list(argv)
        try:
            with redirect_stdout(out), redirect_stderr(err):
                main(args)
        except SystemExit as exc:
            code = exc.code
        return code, out.getvalue(), err.getvalue()


class TestListCommands(CLITestCase):
    def test_no_command_exits_1(self):
        code, out, _ = self.run_cli(db=False)
        self.assertEqual(code, 1)
        self.assertIn("usage:", out)

    def test_inbox(self):
        code, out, _ = self.run_cli("inbox")
        self.assertEqual(code, 0)
        self.assertIn("Inbox Item 1", out)
        self.assertIn("Inbox Item 2", out)

    def test_inbox_count(self):
        code, out, _ = self.run_cli("inbox", "--count")
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "2")

    def test_next_show_project(self):
        code, out, _ = self.run_cli("next", "-p")
        self.assertEqual(code, 0)
        self.assertIn("Project", out)  # column header
        self.assertIn("Test Project", out)

    def test_next_show_created(self):
        code, out, _ = self.run_cli("next", "-c")
        self.assertEqual(code, 0)
        self.assertIn("Created", out)  # column header
        self.assertIn("2023-11-14", out)

    def test_search_combined_flags_table(self):
        code, out, _ = self.run_cli("search", "-a", "-p", "-c", "task")
        self.assertEqual(code, 0)
        header = next(line for line in out.splitlines() if line.startswith("ID"))
        for column in ("ID", "Title", "Project", "Created"):
            self.assertIn(column, header)
        self.assertLess(header.index("Project"), header.index("Title"))
        self.assertIn("Done Task", out)
        self.assertIn("Test Project", out)

    def test_next_by_project_name(self):
        code, out, _ = self.run_cli("next", "--project", "Test Project")
        self.assertEqual(code, 0)
        self.assertIn("Active Task", out)

    def test_next_unknown_project_exits_1(self):
        code, _, err = self.run_cli("next", "--project", "nonexistent")
        self.assertEqual(code, 1)
        self.assertIn("No project found", err)

    def test_done_show_completed(self):
        code, out, _ = self.run_cli("done", "-d")
        self.assertEqual(code, 0)
        self.assertIn("Done Task", out)
        self.assertIn("2023-11-14", out)  # completion date column

    def test_done_count_ignores_limit(self):
        code, out, _ = self.run_cli("done", "--count", "-n", "0")
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "3")

    def test_search(self):
        code, out, _ = self.run_cli("search", "focused")
        self.assertEqual(code, 0)
        self.assertIn("Focused Task", out)

    def test_search_excludes_done_by_default(self):
        code, out, _ = self.run_cli("search", "task")
        self.assertEqual(code, 0)
        self.assertNotIn("Done Task", out)

    def test_search_all_includes_done(self):
        code, out, _ = self.run_cli("search", "--all", "task")
        self.assertEqual(code, 0)
        self.assertIn("Done Task", out)
        self.assertIn("Active Task", out)

    def test_search_multiple_queries_or_combined(self):
        code, out, _ = self.run_cli("search", "Waiting", "Someday")
        self.assertEqual(code, 0)
        self.assertIn("Waiting For Bob", out)
        self.assertIn("Someday Idea", out)

    def test_search_multiple_queries_dedupe_by_id(self):
        # both terms match the same item; it must appear only once
        code, out, _ = self.run_cli("search", "--count", "Waiting", "Bob")
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "1")

    def test_search_titles_output(self):
        code, out, _ = self.run_cli("search", "-a", "-t", "task")
        self.assertEqual(code, 0)
        lines = out.strip().splitlines()
        self.assertEqual(lines, ["Active Task", "Done Task", "Focused Task"])

    def test_search_titles_with_project_context(self):
        code, out, _ = self.run_cli("search", "-a", "-t", "-p", "task")
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertEqual(lines[0], "")
        # header has no "Done" label; Task starts after the 2-char mark column
        self.assertTrue(lines[1].startswith("   Task"))
        self.assertTrue(lines[1].endswith("Project(s)"))
        self.assertEqual(set(lines[2]), {"-"})
        rows = lines[3:]
        self.assertEqual(len(rows), 3)
        by_title = {row.split("  ")[1].strip(): row for row in rows}
        self.assertTrue(by_title["Done Task"].startswith("✓"))
        self.assertTrue(by_title["Active Task"].startswith("   "))
        self.assertTrue(by_title["Focused Task"].startswith("   "))
        for row in rows:
            self.assertTrue(row.endswith("Test Project"))

    def test_search_titles_without_project_for_parentless_items(self):
        code, out, _ = self.run_cli("search", "-t", "-p", "inbox")
        self.assertEqual(code, 0)
        lines = out.strip().splitlines()
        rows = lines[2:]
        self.assertEqual(len(rows), 2)
        self.assertIn("Inbox Item 1", rows[0])
        self.assertIn("Inbox Item 2", rows[1])
        for row in rows:
            self.assertTrue(row.startswith("   "))  # open, no checkmark
            self.assertNotIn("Test Project", row)


class TestDetailCommands(CLITestCase):
    def test_projects_summary(self):
        code, out, _ = self.run_cli("projects")
        self.assertEqual(code, 0)
        self.assertIn("Test Project", out)
        self.assertNotIn("Old Trip 2024", out)
        self.assertIn("Created", out)
        self.assertIn("2023-11-14", out)  # TS_BASE as UTC date

    def test_projects_list_archived(self):
        code, out, _ = self.run_cli("projects", "--list", "archived")
        self.assertEqual(code, 0)
        self.assertIn("Old Trip 2024", out)
        self.assertNotIn("Test Project", out)

    def test_projects_list_all(self):
        code, out, _ = self.run_cli("projects", "--list", "all")
        self.assertEqual(code, 0)
        self.assertIn("Old Trip 2024", out)
        self.assertIn("Test Project", out)

    def test_projects_filter_title(self):
        code, out, _ = self.run_cli("projects", "--list", "all", "--filter", "trip")
        self.assertEqual(code, 0)
        self.assertIn("Old Trip 2024", out)
        self.assertNotIn("Test Project", out)

    def test_projects_filter_without_list(self):
        code, out, _ = self.run_cli("projects", "--filter", "trip")
        self.assertEqual(code, 0)
        self.assertNotIn("Old Trip 2024", out)  # archived, not in default view
        self.assertIn("(none)", out)

    def test_projects_default_sort_created_desc(self):
        code, out, _ = self.run_cli("projects", "--list", "all")
        self.assertEqual(code, 0)
        # Test Project (TS_BASE) is newer than Old Trip 2024 (TS_BASE - 1000)
        self.assertLess(out.index("Test Project"), out.index("Old Trip 2024"))

    def test_projects_sort_title(self):
        code, out, _ = self.run_cli("projects", "--list", "all", "--sort", "title")
        self.assertEqual(code, 0)
        self.assertLess(out.index("Old Trip 2024"), out.index("Test Project"))

    def test_projects_sort_reverse(self):
        code, out, _ = self.run_cli("projects", "--list", "all", "--reverse")
        self.assertEqual(code, 0)
        self.assertLess(out.index("Old Trip 2024"), out.index("Test Project"))


class TestTasksCommand(CLITestCase):
    def test_tasks_by_project_name(self):
        code, out, _ = self.run_cli("tasks", "Test Project")
        self.assertEqual(code, 0)
        for title in ("Active Task", "Focused Task", "Done Task"):
            self.assertIn(title, out)

    def test_tasks_of_archived_project(self):
        code, out, _ = self.run_cli("tasks", "Old Trip")
        self.assertEqual(code, 0)
        self.assertIn("Pack Tent", out)
        self.assertIn("pack tent", out)  # list mode shows both duplicates

    def test_tasks_multiple_projects_titles_deduped(self):
        code, out, _ = self.run_cli("tasks", "-t", "Test Project", "Old Trip")
        self.assertEqual(code, 0)
        self.assertEqual(
            out.strip().splitlines(),
            ["Active Task", "Done Task", "Focused Task", "Pack Tent"],
        )

    def test_tasks_titles_table_with_checkmark(self):
        code, out, _ = self.run_cli("tasks", "-t", "-p", "Old Trip")
        self.assertEqual(code, 0)
        rows = out.splitlines()[3:]
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0].startswith("✓  Pack Tent"))
        self.assertTrue(rows[0].endswith("Old Trip 2024"))

    def test_tasks_unknown_project_exits_1(self):
        code, _, err = self.run_cli("tasks", "nonexistent")
        self.assertEqual(code, 1)
        self.assertIn("No project found", err)

    def test_tasks_count_counts_items_not_titles(self):
        code, out, _ = self.run_cli("tasks", "--count", "Old Trip")
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "2")

    def test_show_by_prefix(self):
        code, out, _ = self.run_cli("show", PROJECT_ID[:8])
        self.assertEqual(code, 0)
        self.assertIn("Test Project", out)

    def test_show_non_hex_id_exits_1(self):
        code, _, err = self.run_cli("show", "not-a-hex-id")
        self.assertEqual(code, 1)
        self.assertIn("Item not found", err)

    def test_project_detail(self):
        code, out, _ = self.run_cli("project", PROJECT_ID[:8])
        self.assertEqual(code, 0)
        self.assertIn("Test Project", out)
        self.assertIn("Tasks", out)

    def test_project_rejects_non_project(self):
        code, _, err = self.run_cli("project", ACTION_ACTIVE_ID[:8])
        self.assertEqual(code, 1)
        self.assertIn("Not a project", err)

    def test_tags_filtered(self):
        code, out, _ = self.run_cli("tags", "--type", "area")
        self.assertEqual(code, 0)
        self.assertIn("Work", out)
        self.assertNotIn("Alice", out)


class TestDatabaseErrors(unittest.TestCase):
    def test_missing_db_exits_1_with_message(self):
        out, err = io.StringIO(), io.StringIO()
        code = 0
        try:
            with redirect_stdout(out), redirect_stderr(err):
                main(["--db", "/nonexistent/path/db", "inbox"])
        except SystemExit as exc:
            code = exc.code
        self.assertEqual(code, 1)
        self.assertIn("Cannot open database", err.getvalue())


class TestInboxAddCommand(unittest.TestCase):
    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        code = 0
        try:
            with redirect_stdout(out), redirect_stderr(err):
                main(list(argv))
        except SystemExit as exc:
            code = exc.code
        return code, out.getvalue(), err.getvalue()

    def test_help_lists_inbox_add_options_without_timeout(self):
        code, out, _ = self.run_cli("inbox-add", "--help")
        self.assertEqual(code, 0)
        for option in ("--note", "--focused", "--api-url", "--api-key"):
            self.assertIn(option, out)
        self.assertNotIn("--timeout", out)

    def test_uses_default_url_and_key_flag(self):
        created = CreatedInboxItem("abc", datetime(2026, 8, 14, 12, 34, 56, tzinfo=timezone.utc))
        with patch.dict(os.environ, {}, clear=True), patch("everdo.main.EverdoAPI") as api_cls:
            api_cls.return_value.create_inbox_item.return_value = created
            code, out, err = self.run_cli("inbox-add", "Title", "--api-key", "flag-key")
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        api_cls.assert_called_once_with("https://localhost:11111", "flag-key")
        self.assertIn("abc", out)
        self.assertIn("2026-08-14 12:34:56 UTC", out)

    def test_does_not_open_database_for_inbox_add(self):
        with patch("everdo.main.EverdoDB") as db_cls, patch("everdo.main.EverdoAPI") as api_cls:
            api_cls.return_value.create_inbox_item.return_value = Mock(
                id="abc", created_on=datetime(2026, 1, 1, tzinfo=timezone.utc)
            )
            code, _, err = self.run_cli("--db", "/definitely/missing/db", "inbox-add", "Title", "--api-key", "key")
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        db_cls.assert_not_called()

    def test_flags_override_environment_and_forward_optional_values(self):
        created = Mock(id="abc", created_on=datetime(2026, 1, 1, tzinfo=timezone.utc))
        with patch.dict(os.environ, {"EVERDO_API_URL": "env-url", "EVERDO_API_KEY": "env-key"}), patch(
            "everdo.main.EverdoAPI"
        ) as api_cls:
            api_cls.return_value.create_inbox_item.return_value = created
            code, _, _ = self.run_cli(
                "inbox-add",
                "Title",
                "--note",
                "Details",
                "--focused",
                "--api-url",
                "flag-url",
                "--api-key",
                "flag-key",
            )
        self.assertEqual(code, 0)
        api_cls.assert_called_once_with("flag-url", "flag-key")
        api_cls.return_value.create_inbox_item.assert_called_once_with(
            "Title", note="Details", is_focused=True
        )

    def test_uses_environment_fallback(self):
        with patch.dict(os.environ, {"EVERDO_API_URL": "env-url", "EVERDO_API_KEY": "env-key"}), patch(
            "everdo.main.EverdoAPI"
        ) as api_cls:
            api_cls.return_value.create_inbox_item.return_value = Mock(
                id="abc", created_on=datetime(2026, 1, 1, tzinfo=timezone.utc)
            )
            code, _, _ = self.run_cli("inbox-add", "Title")
        self.assertEqual(code, 0)
        api_cls.assert_called_once_with("env-url", "env-key")

    def test_explicit_empty_api_key_does_not_fall_back_to_environment(self):
        with patch.dict(os.environ, {"EVERDO_API_KEY": "env-key"}), patch("everdo.main.EverdoAPI") as api_cls:
            code, out, err = self.run_cli("inbox-add", "Title", "--api-key", "")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("API key", err)
        api_cls.assert_not_called()

    def test_explicit_empty_api_url_does_not_fall_back_to_environment(self):
        with patch.dict(os.environ, {"EVERDO_API_URL": "env-url", "EVERDO_API_KEY": "env-key"}), patch(
            "everdo.main.EverdoAPI"
        ) as api_cls:
            code, out, err = self.run_cli("inbox-add", "Title", "--api-url", "")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertEqual(err, "Cannot create inbox item: API URL must not be empty\n")
        api_cls.assert_not_called()

    def test_empty_environment_api_key_is_missing(self):
        with patch.dict(os.environ, {"EVERDO_API_KEY": ""}), patch("everdo.main.EverdoAPI") as api_cls:
            code, out, err = self.run_cli("inbox-add", "Title")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("API key", err)
        api_cls.assert_not_called()

    def test_empty_environment_api_url_uses_default(self):
        with patch.dict(os.environ, {"EVERDO_API_URL": "", "EVERDO_API_KEY": "env-key"}), patch(
            "everdo.main.EverdoAPI"
        ) as api_cls:
            api_cls.return_value.create_inbox_item.return_value = Mock(
                id="abc", created_on=datetime(2026, 1, 1, tzinfo=timezone.utc)
            )
            code, _, _ = self.run_cli("inbox-add", "Title")
        self.assertEqual(code, 0)
        api_cls.assert_called_once_with("https://localhost:11111", "env-key")

    def test_missing_key_errors_before_client_creation(self):
        with patch.dict(os.environ, {}, clear=True), patch("everdo.main.EverdoAPI") as api_cls:
            code, out, err = self.run_cli("inbox-add", "Title")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("API key", err)
        api_cls.assert_not_called()

    def test_whitespace_title_error_is_propagated_from_client(self):
        with patch("everdo.main.EverdoAPI") as api_cls:
            api_cls.return_value.create_inbox_item.side_effect = EverdoAPIError("Title must not be empty")
            code, out, err = self.run_cli("inbox-add", "   ", "--api-key", "key")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("Cannot create inbox item: Title must not be empty", err)

    def test_client_connection_failure_is_reported_on_stderr(self):
        with patch("everdo.main.EverdoAPI") as api_cls:
            api_cls.return_value.create_inbox_item.side_effect = EverdoAPIError("Cannot connect to Everdo API")
            code, out, err = self.run_cli("inbox-add", "Title", "--api-key", "key")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertEqual(err, "Cannot create inbox item: Cannot connect to Everdo API\n")

    def test_success_returns_zero_and_prints_id_and_created_on(self):
        created = CreatedInboxItem("abc", datetime(2026, 8, 14, 12, 34, 56, tzinfo=timezone.utc))
        with patch("everdo.main.EverdoAPI") as api_cls:
            api_cls.return_value.create_inbox_item.return_value = created
            code, out, err = self.run_cli("inbox-add", "Title", "--api-key", "key")
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertEqual(out, "abc\t2026-08-14 12:34:56 UTC\n")

    def test_success_converts_created_on_to_utc(self):
        with patch("everdo.main.EverdoAPI") as api_cls:
            api_cls.return_value.create_inbox_item.return_value = CreatedInboxItem(
                "abc", datetime(2026, 8, 14, 14, 34, 56, tzinfo=timezone(timedelta(hours=2)))
            )
            code, out, err = self.run_cli("inbox-add", "Title", "--api-key", "key")
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertEqual(out, "abc\t2026-08-14 12:34:56 UTC\n")


if __name__ == "__main__":
    unittest.main()
