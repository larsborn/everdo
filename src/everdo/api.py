#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import socket
import ssl
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib import parse, request
from urllib.error import HTTPError, URLError

DEFAULT_API_URL = "https://localhost:11111"
API_TIMEOUT_SECONDS = 30


class EverdoAPIError(Exception):
    """Raised when the Everdo API cannot complete an expected operation."""


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
        if not title.strip():
            raise EverdoAPIError("Title must not be empty")

        try:
            with request.urlopen(req, timeout=API_TIMEOUT_SECONDS, context=context) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise EverdoAPIError(f"Everdo API returned HTTP {error.code}") from None
        except (socket.timeout, TimeoutError):
            raise EverdoAPIError("Everdo API timed out after 30 seconds") from None
        except URLError as error:
            if isinstance(error.reason, (socket.timeout, TimeoutError)):
                raise EverdoAPIError("Everdo API timed out after 30 seconds") from None
            raise EverdoAPIError("Cannot connect to Everdo API") from None
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise EverdoAPIError("Everdo API returned invalid JSON") from None

        try:
            item_id = response_data["id"]
            created_timestamp = response_data["createdOn"]
            if (
                not isinstance(item_id, str)
                or not isinstance(created_timestamp, (int, float))
                or isinstance(created_timestamp, bool)
            ):
                raise TypeError
            created_on = datetime.fromtimestamp(created_timestamp, tz=timezone.utc)
        except (KeyError, IndexError, TypeError, ValueError, OverflowError, OSError):
            raise EverdoAPIError("Everdo API returned an invalid response") from None

        return CreatedInboxItem(id=item_id, created_on=created_on)
