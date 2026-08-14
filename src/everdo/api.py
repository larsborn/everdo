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
