#!/usr/bin/env python
# -*- coding: utf-8 -*-
import io
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

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
        self.assertIn("[Test Project]", out)

    def test_next_show_created(self):
        code, out, _ = self.run_cli("next", "-c")
        self.assertEqual(code, 0)
        self.assertIn("created:2023-11-14", out)

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
        self.assertIn("done:2023-11-14", out)

    def test_done_count_ignores_limit(self):
        code, out, _ = self.run_cli("done", "--count", "-n", "0")
        self.assertEqual(code, 0)
        self.assertEqual(out.strip(), "1")

    def test_search(self):
        code, out, _ = self.run_cli("search", "focused")
        self.assertEqual(code, 0)
        self.assertIn("Focused Task", out)


class TestDetailCommands(CLITestCase):
    def test_projects_summary(self):
        code, out, _ = self.run_cli("projects")
        self.assertEqual(code, 0)
        self.assertIn("Test Project", out)

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


if __name__ == "__main__":
    unittest.main()
