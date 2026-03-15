#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime, timezone


class ItemType(enum.Enum):
    ACTION = "a"
    PROJECT = "p"
    NOTEBOOK = "l"
    NOTE = "n"


class ListType(enum.Enum):
    INBOX = "i"
    ACTIVE = "a"
    SCHEDULED = "s"
    WAITING = "w"
    SOMEDAY = "m"
    DELETED = "d"
    ARCHIVED = "r"


class TagType(enum.Enum):
    AREA = "a"
    CONTACT = "c"
    LABEL = "l"


class Energy(enum.IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3


def _ts_to_datetime(ts: int | None) -> datetime | None:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)


@dataclass(frozen=True)
class Tag:
    id: str
    title: str
    type: TagType
    color: int | None = None

    def __str__(self) -> str:
        return self.title


@dataclass(frozen=True)
class Item:
    id: str
    title: str
    type: ItemType
    list_type: ListType
    created_on: datetime | None = None
    completed_on: datetime | None = None
    is_focused: bool = False
    due_date: datetime | None = None
    start_date: datetime | None = None
    parent_id: str | None = None
    note: str | None = None
    time: int | None = None
    energy: int | None = None
    schedule: str | None = None
    contact_id: str | None = None
    tags: list[Tag] = field(default_factory=list)

    @property
    def is_complete(self) -> bool:
        return self.completed_on is not None

    @property
    def short_id(self) -> str:
        return self.id[:8]

    @property
    def is_recurring(self) -> bool:
        return self.schedule is not None and self.schedule != ""

    @property
    def has_parent(self) -> bool:
        return self.parent_id is not None
