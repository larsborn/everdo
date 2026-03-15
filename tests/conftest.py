#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Shared test fixtures — builds a temp SQLite database with known data."""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from pathlib import Path

from everdo.db import EverdoDB

# Fixed 16-byte IDs as hex strings
TAG_AREA_ID = "aa" * 16
TAG_CONTACT_ID = "bb" * 16
TAG_LABEL_ID = "cc" * 16

PROJECT_ID = "01" * 16
ACTION_DONE_ID = "02" * 16
ACTION_FOCUSED_ID = "03" * 16
ACTION_ACTIVE_ID = "04" * 16
INBOX_1_ID = "05" * 16
INBOX_2_ID = "06" * 16
SCHEDULED_ID = "07" * 16
WAITING_ID = "08" * 16
SOMEDAY_ID = "09" * 16
NOTEBOOK_ID = "0a" * 16
NOTE_1_ID = "0b" * 16
NOTE_2_ID = "0c" * 16

TS_BASE = 1700000000  # a fixed timestamp in seconds since epoch


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE item_type (id VARCHAR(1) PRIMARY KEY, title VARCHAR(50));
        CREATE TABLE item_list (id VARCHAR(1) PRIMARY KEY, title VARCHAR(50));
        CREATE TABLE tag_type (id VARCHAR(1) PRIMARY KEY, title VARCHAR(50));

        CREATE TABLE item (
            id BLOB PRIMARY KEY,
            title VARCHAR(255) NOT NULL,
            note TEXT,
            type VARCHAR(1) NOT NULL REFERENCES item_type(id),
            list VARCHAR(1) NOT NULL REFERENCES item_list(id),
            created_on INTEGER NOT NULL,
            is_focused INTEGER NOT NULL DEFAULT 0,
            completed_on INTEGER,
            schedule VARCHAR NULL,
            due_date INTEGER,
            start_date INTEGER,
            parent_id BLOB NULL,
            time INTEGER NULL,
            energy INTEGER NULL,
            contact_id BLOB NULL,
            position_child INTEGER
        );
        CREATE INDEX idx_item_type ON item(type);
        CREATE INDEX idx_item_list ON item(list);
        CREATE INDEX idx_item_parentid ON item(parent_id);

        CREATE TABLE tag (
            id BLOB PRIMARY KEY,
            type VARCHAR(1) NOT NULL REFERENCES tag_type(id),
            title VARCHAR(50) NOT NULL,
            color INTEGER
        );
        CREATE INDEX idx_tag_type ON tag(type);

        CREATE TABLE tagitem (
            tag_id BLOB,
            item_id BLOB,
            PRIMARY KEY (tag_id, item_id)
        );
        CREATE INDEX idx_tagitem_itemid ON tagitem(item_id);
        CREATE INDEX idx_tagitem_tagid ON tagitem(tag_id);
    """)


def _populate(conn: sqlite3.Connection) -> None:
    conn.executemany(
        "INSERT INTO item_type VALUES (?, ?)",
        [
            ("a", "Action"),
            ("p", "Project"),
            ("l", "Reference List"),
            ("n", "Reference Note"),
        ],
    )
    conn.executemany(
        "INSERT INTO item_list VALUES (?, ?)",
        [
            ("i", "Inbox"),
            ("a", "Active/Next"),
            ("m", "Someday/Maybe"),
            ("s", "Scheduled"),
            ("w", "Waiting for someone"),
            ("d", "Deleted/Trash"),
            ("r", "Archived"),
        ],
    )
    conn.executemany(
        "INSERT INTO tag_type VALUES (?, ?)",
        [("l", "Label"), ("a", "Area"), ("c", "Contact")],
    )

    conn.executemany(
        "INSERT INTO tag VALUES (?, ?, ?, ?)",
        [
            (bytes.fromhex(TAG_AREA_ID), "a", "Work", None),
            (bytes.fromhex(TAG_CONTACT_ID), "c", "Alice", None),
            (bytes.fromhex(TAG_LABEL_ID), "l", "urgent", 1),
        ],
    )

    def _ins(
        item_id,
        title,
        typ,
        lst,
        created=TS_BASE,
        focused=0,
        completed=None,
        schedule=None,
        due=None,
        start=None,
        parent=None,
        time_=None,
        energy=None,
        contact=None,
        note=None,
        pos_child=0,
    ):
        conn.execute(
            "INSERT INTO item VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                bytes.fromhex(item_id),
                title,
                note,
                typ,
                lst,
                created,
                focused,
                completed,
                schedule,
                due,
                start,
                bytes.fromhex(parent) if parent else None,
                time_,
                energy,
                bytes.fromhex(contact) if contact else None,
                pos_child,
            ),
        )

    _ins(PROJECT_ID, "Test Project", "p", "a", energy=2, pos_child=0)
    _ins(
        ACTION_DONE_ID,
        "Done Task",
        "a",
        "a",
        completed=TS_BASE + 1,
        parent=PROJECT_ID,
        pos_child=0,
    )
    _ins(
        ACTION_FOCUSED_ID,
        "Focused Task",
        "a",
        "a",
        focused=1,
        parent=PROJECT_ID,
        energy=3,
        time_=30,
        pos_child=1,
    )
    _ins(
        ACTION_ACTIVE_ID,
        "Active Task",
        "a",
        "a",
        parent=PROJECT_ID,
        due=TS_BASE + 86400,
        pos_child=2,
    )
    _ins(INBOX_1_ID, "Inbox Item 1", "a", "i")
    _ins(INBOX_2_ID, "Inbox Item 2", "a", "i")
    _ins(SCHEDULED_ID, "Scheduled Thing", "a", "s", start=TS_BASE + 172800)
    _ins(WAITING_ID, "Waiting For Bob", "a", "w", contact=TAG_CONTACT_ID)
    _ins(SOMEDAY_ID, "Someday Idea", "a", "m", schedule="weekly")
    _ins(NOTEBOOK_ID, "My Notebook", "l", "a")
    _ins(NOTE_1_ID, "Note Alpha", "n", "a", parent=NOTEBOOK_ID, note="Some note text")
    _ins(NOTE_2_ID, "Note Beta", "n", "a", parent=NOTEBOOK_ID)

    conn.executemany(
        "INSERT INTO tagitem VALUES (?, ?)",
        [
            (bytes.fromhex(TAG_AREA_ID), bytes.fromhex(PROJECT_ID)),
            (bytes.fromhex(TAG_LABEL_ID), bytes.fromhex(ACTION_FOCUSED_ID)),
            (bytes.fromhex(TAG_CONTACT_ID), bytes.fromhex(WAITING_ID)),
            (bytes.fromhex(TAG_AREA_ID), bytes.fromhex(INBOX_1_ID)),
        ],
    )
    conn.commit()


def create_test_db(directory: str | Path) -> Path:
    """Create a populated test database in the given directory, return its path."""
    db_file = Path(directory) / "test_everdo.db"
    conn = sqlite3.connect(str(db_file))
    _create_schema(conn)
    _populate(conn)
    conn.close()
    return db_file


def open_test_db(db_path: Path) -> EverdoDB:
    """Open an EverdoDB against a test database (bypasses read-only URI)."""
    edb = EverdoDB.__new__(EverdoDB)
    edb._path = db_path
    edb._conn = sqlite3.connect(str(db_path))
    edb._conn.row_factory = sqlite3.Row
    edb._tags_by_id = {}
    edb._tags_by_item = defaultdict(list)
    edb._load_tags()
    return edb
