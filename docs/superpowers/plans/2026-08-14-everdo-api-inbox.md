# Everdo API Inbox Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `inbox-add` so the CLI can create Everdo Inbox items through the documented HTTPS API using only Python's standard library.

**Architecture:** A focused `EverdoAPI` client owns HTTP, JSON, TLS, response validation, and safe API errors. The CLI resolves flags and environment variables, handles the API command before opening SQLite, and leaves all existing read-only query commands unchanged.

**Tech Stack:** Python 3 standard library (`argparse`, `dataclasses`, `datetime`, `json`, `os`, `ssl`, `urllib`), `unittest`, `unittest.mock`

---

## File Map

- Create `src/everdo/api.py`: API client, typed creation result, fixed timeout, disabled certificate verification, response validation, and redacted client errors.
- Create `tests/test_api.py`: isolated HTTP-client tests using mocks and no network.
- Modify `src/everdo/main.py`: parser options, environment configuration, API command dispatch, output, and exit behavior.
- Modify `tests/test_main.py`: CLI configuration, successful output, failure, and SQLite-isolation tests.
- Modify `README.md`: install/feature wording, command usage, configuration precedence, timeout, and TLS warning.

### Task 1: Successful API Client

**Files:**
- Create: `src/everdo/api.py`
- Create: `tests/test_api.py`

- [ ] **Step 1: Write tests for successful requests and response conversion**

Create `tests/test_api.py` with the successful-path tests below. The response helper behaves as the context manager returned by `urlopen`.

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import ssl
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from everdo.api import EverdoAPI


class TestEverdoAPISuccess(unittest.TestCase):
    def response(self, payload):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(payload).encode("utf-8")
        return response

    @patch("everdo.api.request.urlopen")
    def test_create_inbox_item_sends_documented_request(self, urlopen):
        urlopen.return_value = self.response({"id": "ABCD", "createdOn": 1700000000})

        result = EverdoAPI("https://localhost:11111/", "a key").create_inbox_item(
            "Café beans", note="Buy two bags", is_focused=True
        )

        request_obj = urlopen.call_args.args[0]
        self.assertEqual(request_obj.full_url, "https://localhost:11111/api/items/?key=a+key")
        self.assertEqual(request_obj.get_method(), "POST")
        self.assertEqual(request_obj.get_header("Content-type"), "application/json")
        self.assertEqual(
            json.loads(request_obj.data.decode("utf-8")),
            {"title": "Café beans", "note": "Buy two bags", "isFocused": True},
        )
        self.assertEqual(result.id, "ABCD")
        self.assertEqual(result.created_on, datetime.fromtimestamp(1700000000, tz=timezone.utc))

    @patch("everdo.api.request.urlopen")
    def test_create_uses_fixed_timeout_and_unverified_ssl_context(self, urlopen):
        urlopen.return_value = self.response({"id": "ABCD", "createdOn": 1700000000})

        EverdoAPI("https://localhost:11111", "secret").create_inbox_item("Title")

        self.assertEqual(urlopen.call_args.kwargs["timeout"], 30)
        context = urlopen.call_args.kwargs["context"]
        self.assertIsInstance(context, ssl.SSLContext)
        self.assertFalse(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_NONE)

    @patch("everdo.api.request.urlopen")
    def test_create_omits_optional_fields_by_default(self, urlopen):
        urlopen.return_value = self.response({"id": "ABCD", "createdOn": 1700000000})

        EverdoAPI("https://localhost:11111", "secret").create_inbox_item("Title")

        request_obj = urlopen.call_args.args[0]
        self.assertEqual(json.loads(request_obj.data.decode("utf-8")), {"title": "Title"})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the client tests and confirm the expected import failure**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_api -v
```

Expected: `ERROR` with `ModuleNotFoundError: No module named 'everdo.api'`.

- [ ] **Step 3: Implement the minimal successful API client**

Create `src/everdo/api.py`:

```python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib import parse, request

DEFAULT_API_URL = "https://localhost:11111"
API_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class CreatedInboxItem:
    id: str
    created_on: datetime


class EverdoAPI:
    def __init__(self, base_url: str, api_key: str):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key

    def create_inbox_item(
        self,
        title: str,
        *,
        note: str | None = None,
        is_focused: bool = False,
    ) -> CreatedInboxItem:
        payload: dict[str, object] = {"title": title}
        if note is not None:
            payload["note"] = note
        if is_focused:
            payload["isFocused"] = True

        query = parse.urlencode({"key": self._api_key})
        req = request.Request(
            f"{self._base_url}/api/items/?{query}",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        context = ssl._create_unverified_context()
        with request.urlopen(req, timeout=API_TIMEOUT_SECONDS, context=context) as response:
            response_data = json.loads(response.read().decode("utf-8"))
        return CreatedInboxItem(
            id=response_data["id"],
            created_on=datetime.fromtimestamp(response_data["createdOn"], tz=timezone.utc),
        )
```

- [ ] **Step 4: Run the successful client tests**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_api.TestEverdoAPISuccess -v
```

Expected: 3 tests pass.

- [ ] **Step 5: Commit the successful client**

```bash
git add src/everdo/api.py tests/test_api.py
git commit -m "feat; add Everdo inbox API client"
```

### Task 2: API Validation and Safe Errors

**Files:**
- Modify: `src/everdo/api.py`
- Modify: `tests/test_api.py`

- [ ] **Step 1: Add failing tests for validation and each expected failure category**

Add these imports to `tests/test_api.py`:

```python
import socket
from urllib import error

from everdo.api import EverdoAPI, EverdoAPIError
```

Add this test class before the `if __name__ == "__main__"` block:

```python
class TestEverdoAPIErrors(unittest.TestCase):
    def assert_api_error(self, side_effect, expected_text):
        with patch("everdo.api.request.urlopen", side_effect=side_effect):
            with self.assertRaisesRegex(EverdoAPIError, expected_text) as caught:
                EverdoAPI("https://localhost:11111", "top-secret").create_inbox_item("Title")
        self.assertNotIn("top-secret", str(caught.exception))

    def test_rejects_empty_title_without_network(self):
        with patch("everdo.api.request.urlopen") as urlopen:
            with self.assertRaisesRegex(EverdoAPIError, "Title must not be empty"):
                EverdoAPI("https://localhost:11111", "secret").create_inbox_item("   ")
        urlopen.assert_not_called()

    def test_reports_connection_error_without_leaking_key(self):
        self.assert_api_error(error.URLError("connection refused"), "Cannot connect to Everdo API")

    def test_reports_timeout(self):
        self.assert_api_error(error.URLError(socket.timeout()), "timed out after 30 seconds")

    def test_reports_http_status_without_leaking_request_url(self):
        failure = error.HTTPError(
            "https://localhost:11111/api/items/?key=top-secret", 401, "Unauthorized", {}, None
        )
        self.assert_api_error(failure, "HTTP 401: Unauthorized")

    @patch("everdo.api.request.urlopen")
    def test_rejects_invalid_json(self, urlopen):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b"not-json"
        urlopen.return_value = response
        with self.assertRaisesRegex(EverdoAPIError, "invalid JSON"):
            EverdoAPI("https://localhost:11111", "secret").create_inbox_item("Title")

    def test_rejects_missing_or_invalid_response_fields(self):
        invalid_payloads = [
            {},
            {"id": "ABCD"},
            {"id": 123, "createdOn": 1700000000},
            {"id": "ABCD", "createdOn": "yesterday"},
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                response = MagicMock()
                response.__enter__.return_value.read.return_value = json.dumps(payload).encode("utf-8")
                with patch("everdo.api.request.urlopen", return_value=response):
                    with self.assertRaisesRegex(EverdoAPIError, "invalid response"):
                        EverdoAPI("https://localhost:11111", "secret").create_inbox_item("Title")
```

- [ ] **Step 2: Run the error tests and verify they fail**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_api.TestEverdoAPIErrors -v
```

Expected: import fails because `EverdoAPIError` does not exist.

- [ ] **Step 3: Add the public client exception and safe error conversion**

Add imports in `src/everdo/api.py`:

```python
import socket
from urllib import error, parse, request
```

Replace `from urllib import parse, request` with the combined import above. Add after the constants:

```python
class EverdoAPIError(Exception):
    """An expected configuration, transport, or response failure."""
```

Replace `create_inbox_item()` with:

```python
    def create_inbox_item(
        self,
        title: str,
        *,
        note: str | None = None,
        is_focused: bool = False,
    ) -> CreatedInboxItem:
        if not title.strip():
            raise EverdoAPIError("Title must not be empty")

        payload: dict[str, object] = {"title": title}
        if note is not None:
            payload["note"] = note
        if is_focused:
            payload["isFocused"] = True

        query = parse.urlencode({"key": self._api_key})
        req = request.Request(
            f"{self._base_url}/api/items/?{query}",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            context = ssl._create_unverified_context()
            with request.urlopen(req, timeout=API_TIMEOUT_SECONDS, context=context) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            raise EverdoAPIError(f"Everdo API returned HTTP {exc.code}: {exc.reason}") from None
        except (socket.timeout, TimeoutError):
            raise EverdoAPIError(f"Everdo API timed out after {API_TIMEOUT_SECONDS} seconds") from None
        except error.URLError as exc:
            if isinstance(exc.reason, (socket.timeout, TimeoutError)):
                raise EverdoAPIError(f"Everdo API timed out after {API_TIMEOUT_SECONDS} seconds") from None
            raise EverdoAPIError("Cannot connect to Everdo API") from None
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise EverdoAPIError("Everdo API returned invalid JSON") from None

        try:
            item_id = response_data["id"]
            created_on = response_data["createdOn"]
            if not isinstance(item_id, str) or not isinstance(created_on, (int, float)):
                raise TypeError
            created_at = datetime.fromtimestamp(created_on, tz=timezone.utc)
        except (KeyError, TypeError, ValueError, OverflowError, OSError):
            raise EverdoAPIError("Everdo API returned an invalid response") from None

        return CreatedInboxItem(id=item_id, created_on=created_at)
```

- [ ] **Step 4: Run all API tests**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_api -v
```

Expected: all 9 API tests pass.

- [ ] **Step 5: Commit API validation and error handling**

```bash
git add src/everdo/api.py tests/test_api.py
git commit -m "fix; validate Everdo API responses and errors"
```

### Task 3: `inbox-add` CLI Integration

**Files:**
- Modify: `src/everdo/main.py:5-17,20-152,155-171`
- Modify: `tests/test_main.py:3-10,278-289`

- [ ] **Step 1: Add failing CLI tests for parser, configuration, output, errors, and SQLite isolation**

Add imports to `tests/test_main.py`:

```python
import os
from datetime import datetime, timezone
from unittest.mock import patch

from everdo.api import CreatedInboxItem, EverdoAPIError
```

Add this class before `TestDatabaseErrors`:

```python
class TestInboxAddCommand(CLITestCase):
    @patch.dict(os.environ, {}, clear=True)
    @patch("everdo.main.EverdoAPI")
    def test_uses_default_url_and_key_flag_without_opening_db(self, api_class):
        api_class.return_value.create_inbox_item.return_value = CreatedInboxItem(
            "ABCD", datetime(2023, 11, 14, 22, 13, 20, tzinfo=timezone.utc)
        )

        out, err = io.StringIO(), io.StringIO()
        code = 0
        try:
            with patch("everdo.main.EverdoDB", side_effect=AssertionError("SQLite must not open")):
                with redirect_stdout(out), redirect_stderr(err):
                    main(
                        [
                            "--db",
                            "/definitely/missing/everdo.db",
                            "inbox-add",
                            "New item",
                            "--api-key",
                            "secret",
                        ]
                    )
        except SystemExit as exc:
            code = exc.code

        self.assertEqual(code, 0)
        self.assertEqual(err.getvalue(), "")
        api_class.assert_called_once_with("https://localhost:11111", "secret")
        api_class.return_value.create_inbox_item.assert_called_once_with(
            "New item", note=None, is_focused=False
        )
        self.assertIn("ABCD", out.getvalue())
        self.assertIn("2023-11-14 22:13:20 UTC", out.getvalue())

    @patch("everdo.main.EverdoAPI")
    def test_flags_override_environment_and_pass_optional_fields(self, api_class):
        api_class.return_value.create_inbox_item.return_value = CreatedInboxItem(
            "ABCD", datetime(2023, 11, 14, tzinfo=timezone.utc)
        )
        env = {"EVERDO_API_URL": "https://env:11111", "EVERDO_API_KEY": "env-key"}
        with patch.dict(os.environ, env, clear=False):
            code, _, _ = self.run_cli(
                "inbox-add",
                "New item",
                "--note",
                "Details",
                "--focused",
                "--api-url",
                "https://flag:22222",
                "--api-key",
                "flag-key",
            )
        self.assertEqual(code, 0)
        api_class.assert_called_once_with("https://flag:22222", "flag-key")
        api_class.return_value.create_inbox_item.assert_called_once_with(
            "New item", note="Details", is_focused=True
        )

    @patch("everdo.main.EverdoAPI")
    def test_uses_environment_fallback(self, api_class):
        api_class.return_value.create_inbox_item.return_value = CreatedInboxItem(
            "ABCD", datetime(2023, 11, 14, tzinfo=timezone.utc)
        )
        env = {"EVERDO_API_URL": "https://env:11111", "EVERDO_API_KEY": "env-key"}
        with patch.dict(os.environ, env, clear=False):
            code, _, _ = self.run_cli("inbox-add", "New item")
        self.assertEqual(code, 0)
        api_class.assert_called_once_with("https://env:11111", "env-key")

    @patch.dict(os.environ, {}, clear=True)
    @patch("everdo.main.EverdoAPI")
    def test_missing_key_exits_before_client_creation(self, api_class):
        code, _, err = self.run_cli("inbox-add", "New item")
        self.assertEqual(code, 1)
        self.assertIn("API key is required", err)
        api_class.assert_not_called()

    @patch("everdo.main.EverdoAPI")
    def test_empty_title_exits_with_client_error(self, api_class):
        api_class.return_value.create_inbox_item.side_effect = EverdoAPIError("Title must not be empty")
        code, _, err = self.run_cli("inbox-add", "   ", "--api-key", "secret")
        self.assertEqual(code, 1)
        self.assertIn("Cannot create inbox item: Title must not be empty", err)

    @patch("everdo.main.EverdoAPI")
    def test_client_failure_exits_1_on_stderr(self, api_class):
        api_class.return_value.create_inbox_item.side_effect = EverdoAPIError("Cannot connect to Everdo API")
        code, out, err = self.run_cli("inbox-add", "New item", "--api-key", "secret")
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("Cannot create inbox item: Cannot connect to Everdo API", err)
```

- [ ] **Step 2: Run CLI tests and verify parser failure**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_main.TestInboxAddCommand -v
```

Expected: tests fail because `everdo.main` does not expose `EverdoAPI` and the parser does not know `inbox-add`.

- [ ] **Step 3: Add API imports and parser arguments**

Add `os` to the standard-library imports in `src/everdo/main.py` and add this import after them:

```python
from everdo.api import DEFAULT_API_URL, EverdoAPI, EverdoAPIError
```

Add this parser definition immediately before `return parser`:

```python
    inbox_add_p = sub.add_parser("inbox-add", help="Create an inbox item through the Everdo API")
    inbox_add_p.add_argument("title", help="Inbox item title")
    inbox_add_p.add_argument("--note", default=None, help="Optional item note")
    inbox_add_p.add_argument("--focused", action="store_true", help="Create the item as focused")
    inbox_add_p.add_argument(
        "--api-url",
        default=None,
        help=f"Everdo API base URL (default: EVERDO_API_URL or {DEFAULT_API_URL})",
    )
    inbox_add_p.add_argument("--api-key", default=None, help="Everdo API key (default: EVERDO_API_KEY)")
```

- [ ] **Step 4: Dispatch `inbox-add` before opening SQLite**

Insert this block in `main()` after the no-command check and before the `try: db = EverdoDB(args.db)` block:

```python
    if args.command == "inbox-add":
        api_url = args.api_url or os.environ.get("EVERDO_API_URL") or DEFAULT_API_URL
        api_key = args.api_key or os.environ.get("EVERDO_API_KEY")
        if not api_key:
            print("Cannot create inbox item: API key is required (--api-key or EVERDO_API_KEY)", file=sys.stderr)
            sys.exit(1)
        try:
            created = EverdoAPI(api_url, api_key).create_inbox_item(
                args.title,
                note=args.note,
                is_focused=args.focused,
            )
        except EverdoAPIError as exc:
            print(f"Cannot create inbox item: {exc}", file=sys.stderr)
            sys.exit(1)
        print(f"ID: {created.id}")
        print(f"Created: {created.created_on.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        return
```

- [ ] **Step 5: Run focused and full CLI tests**

Run:

```bash
PYTHONPATH=src python -m unittest tests.test_main.TestInboxAddCommand -v
PYTHONPATH=src python -m unittest tests.test_main -v
```

Expected: all `TestInboxAddCommand` tests pass, then all tests in `tests.test_main` pass.

- [ ] **Step 6: Check actual CLI help without making a request**

Run:

```bash
PYTHONPATH=src python -m everdo inbox-add --help
```

Expected: exit 0; help lists `title`, `--note`, `--focused`, `--api-url`, and `--api-key`, with no `--timeout` option.

- [ ] **Step 7: Commit CLI integration**

```bash
git add src/everdo/main.py tests/test_main.py
git commit -m "feat; add inbox-add CLI command"
```

### Task 4: User Documentation and Complete Verification

**Files:**
- Modify: `README.md:1-20,37-67,272-278,373-378`

- [ ] **Step 1: Update the project description and feature list**

Replace README lines 3-4 with:

```markdown
A zero-dependency Python interface to [Everdo](https://everdo.net/). Query actions, projects, and tags from the
read-only local database, or create Inbox items through Everdo's documented HTTP API.
```

Replace the first feature bullet with these two bullets:

```markdown
- **Safe local queries**: opens the SQLite database in read-only mode; query commands never modify it
- **Inbox capture**: creates Inbox items through Everdo's official API, including notes and focused status
```

- [ ] **Step 2: Add complete `inbox-add` usage and security documentation**

Add this section before `### Global Options`:

````markdown
### Add an Inbox item through the API

First enable the API in Everdo under *Settings -> API*, apply the settings, and restart Everdo. The default endpoint is
`https://localhost:11111`.

```bash
python -m everdo inbox-add "Buy coffee" --api-key YOUR_KEY
python -m everdo inbox-add "Review proposal" --note "Before Friday" --focused --api-key YOUR_KEY
```

For persistent configuration, use environment variables. Explicit flags take precedence over environment variables:

```bash
export EVERDO_API_URL=https://localhost:11111
export EVERDO_API_KEY=YOUR_KEY
python -m everdo inbox-add "Buy coffee"
```

The URL precedence is `--api-url`, `EVERDO_API_URL`, then `https://localhost:11111`. The key precedence is `--api-key`
then `EVERDO_API_KEY`; a key is required. Requests time out after 30 seconds.

Everdo's local API commonly uses a self-signed certificate, so this command intentionally does not verify the HTTPS
certificate. Only connect it to an Everdo instance and network you trust. The API key is passed using the query parameter
required by Everdo; avoid exposing commands containing `--api-key` in shared shell history by preferring
`EVERDO_API_KEY`.
````

Add `inbox-add` to the CLI usage command list and command descriptions near README lines 40-63.

- [ ] **Step 3: Correct the architecture description**

Replace the final `How It Works` paragraph with:

```markdown
Everdo stores its data in a SQLite database at `%APPDATA%\Everdo\db` on Windows. Query commands open that database in
read-only mode (`?mode=ro`), convert its records to Python models, and format them for the CLI. `inbox-add` does not open
SQLite; it sends a JSON `POST` request to Everdo's documented `/api/items/` endpoint using Python's standard library.
IDs are stored as 16-byte BLOBs in SQLite and exposed as 32-character hex strings. Timestamps are converted to UTC
`datetime` objects.
```

- [ ] **Step 4: Run formatting checks and the complete test suite**

Run:

```bash
black --check src tests
isort --check-only src tests
PYTHONPATH=src python -m unittest discover -s tests -v
```

Expected: Black and isort exit 0; every test passes. If either formatter reports changes, run `black src tests` or `isort src tests`, inspect the diff, and rerun all three verification commands.

- [ ] **Step 5: Verify dependency and forbidden-command constraints**

Run:

```bash
rg -n "\b(curl|requests|httpx)\b" src tests
git diff --check
```

Expected: `rg` returns no matches in code/tests; `git diff --check` returns no output. README may mention neither `curl` nor a third-party HTTP package.

- [ ] **Step 6: Inspect the final diff for scope and secret safety**

Run:

```bash
git status --short
git diff -- src/everdo/api.py src/everdo/main.py tests/test_api.py tests/test_main.py README.md
```

Expected: only intended files changed since the preceding commits are listed (normally `README.md`, plus any formatter adjustments); no real API key, generated file, SQLite database, or unrelated change appears.

- [ ] **Step 7: Commit documentation and final formatting**

```bash
git add README.md src/everdo/api.py src/everdo/main.py tests/test_api.py tests/test_main.py
git commit -m "docs; document Everdo API inbox command"
```

- [ ] **Step 8: Re-run final verification against the committed tree**

Run:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
git status --short
```

Expected: all tests pass and `git status --short` produces no output.
