#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import socket
import ssl
import unittest
from urllib.error import HTTPError, URLError
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from everdo.api import EverdoAPI, EverdoAPIError


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
        self.assertIn("Café beans".encode("utf-8"), request_obj.data)
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


class TestEverdoAPIErrors(unittest.TestCase):
    def response(self, body):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = body
        return response

    @patch("everdo.api.request.urlopen")
    def test_rejects_whitespace_only_title_without_network_access(self, urlopen):
        with self.assertRaisesRegex(EverdoAPIError, "Title must not be empty"):
            EverdoAPI("https://localhost:11111", "secret").create_inbox_item(" \t\n")
        urlopen.assert_not_called()

    @patch("everdo.api.request.urlopen")
    def test_connection_error_does_not_leak_api_key(self, urlopen):
        urlopen.side_effect = URLError("connection refused")

        with self.assertRaisesRegex(EverdoAPIError, "Cannot connect to Everdo API") as caught:
            EverdoAPI("https://localhost:11111", "secret-key").create_inbox_item("Title")
        self.assertNotIn("secret-key", str(caught.exception))

    @patch("everdo.api.request.urlopen")
    def test_wrapped_timeout_has_fixed_message(self, urlopen):
        urlopen.side_effect = URLError(socket.timeout("timed out"))

        with self.assertRaisesRegex(EverdoAPIError, "Everdo API timed out after 30 seconds"):
            EverdoAPI("https://localhost:11111", "secret").create_inbox_item("Title")

    @patch("everdo.api.request.urlopen")
    def test_direct_timeout_has_fixed_message(self, urlopen):
        urlopen.side_effect = socket.timeout()

        with self.assertRaisesRegex(EverdoAPIError, "Everdo API timed out after 30 seconds"):
            EverdoAPI("https://localhost:11111", "secret").create_inbox_item("Title")

    @patch("everdo.api.request.urlopen")
    def test_http_error_includes_status_and_reason_without_url_or_key(self, urlopen):
        urlopen.side_effect = HTTPError(
            "https://localhost:11111/api/items/?key=secret-key",
            401,
            "Unauthorized https://localhost:11111?key=secret-key",
            {},
            None,
        )

        with self.assertRaisesRegex(EverdoAPIError, "Everdo API returned HTTP 401$") as caught:
            EverdoAPI("https://localhost:11111", "secret-key").create_inbox_item("Title")
        self.assertNotIn("https://", str(caught.exception))
        self.assertNotIn("secret-key", str(caught.exception))

    @patch("everdo.api.request.urlopen")
    def test_malformed_json_is_rejected(self, urlopen):
        urlopen.return_value = self.response(b"not json")

        with self.assertRaisesRegex(EverdoAPIError, "Everdo API returned invalid JSON"):
            EverdoAPI("https://localhost:11111", "secret").create_inbox_item("Title")

    @patch("everdo.api.request.urlopen")
    def test_invalid_utf8_is_rejected_as_invalid_json(self, urlopen):
        urlopen.return_value = self.response(b"\xff")

        with self.assertRaisesRegex(EverdoAPIError, "Everdo API returned invalid JSON"):
            EverdoAPI("https://localhost:11111", "secret").create_inbox_item("Title")

    @patch("everdo.api.request.urlopen")
    def test_invalid_response_payloads_are_rejected(self, urlopen):
        for payload in (
            {},
            {"id": "ABCD"},
            {"id": 123, "createdOn": 1700000000},
            {"id": "ABCD", "createdOn": "1700000000"},
            {"id": "ABCD", "createdOn": True},
            {"id": "ABCD", "createdOn": False},
        ):
            with self.subTest(payload=payload):
                urlopen.return_value = self.response(json.dumps(payload).encode("utf-8"))
                with self.assertRaisesRegex(EverdoAPIError, "Everdo API returned an invalid response"):
                    EverdoAPI("https://localhost:11111", "secret").create_inbox_item("Title")

    @patch("everdo.api.request.urlopen")
    def test_timestamp_conversion_failure_is_rejected_as_invalid_response(self, urlopen):
        urlopen.return_value = self.response(json.dumps({"id": "ABCD", "createdOn": 1700000000}).encode("utf-8"))

        with patch("everdo.api.datetime") as datetime_class:
            datetime_class.fromtimestamp.side_effect = OverflowError
            with self.assertRaisesRegex(EverdoAPIError, "Everdo API returned an invalid response"):
                EverdoAPI("https://localhost:11111", "secret").create_inbox_item("Title")


if __name__ == "__main__":
    unittest.main()
