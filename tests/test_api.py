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


if __name__ == "__main__":
    unittest.main()
