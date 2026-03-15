#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sqlite3
from collections import defaultdict
from pathlib import Path

from everdo.model import Item, ItemType, ListType, Tag, TagType, _ts_to_datetime


def default_db_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "Everdo" / "db"
    return Path.home() / "AppData" / "Roaming" / "Everdo" / "db"


class EverdoDB:
    def __init__(self, db_path: str | Path | None = None):
        if db_path is None:
            db_path = default_db_path()
        self._path = Path(db_path)
        self._conn = sqlite3.connect(f"file:{self._path}?mode=ro", uri=True)
        self._conn.row_factory = sqlite3.Row
        self._tags_by_id: dict[str, Tag] = {}
        self._tags_by_item: dict[str, list[Tag]] = defaultdict(list)
        self._load_tags()

    def _load_tags(self) -> None:
        cur = self._conn.cursor()
        for row in cur.execute("SELECT id, title, type, color FROM tag"):
            tag_id = row["id"].hex()
            self._tags_by_id[tag_id] = Tag(
                id=tag_id,
                title=row["title"],
                type=TagType(row["type"]),
                color=row["color"],
            )
        for row in cur.execute("SELECT tag_id, item_id FROM tagitem"):
            tag_hex = row["tag_id"].hex()
            item_hex = row["item_id"].hex()
            tag = self._tags_by_id.get(tag_hex)
            if tag:
                self._tags_by_item[item_hex].append(tag)

    def _row_to_item(self, row: sqlite3.Row) -> Item:
        item_id = row["id"].hex()
        parent_raw = row["parent_id"]
        return Item(
            id=item_id,
            title=row["title"],
            type=ItemType(row["type"]),
            list_type=ListType(row["list"]),
            created_on=_ts_to_datetime(row["created_on"]),
            completed_on=_ts_to_datetime(row["completed_on"]),
            is_focused=bool(row["is_focused"]),
            due_date=_ts_to_datetime(row["due_date"]),
            start_date=_ts_to_datetime(row["start_date"]),
            parent_id=parent_raw.hex() if parent_raw else None,
            note=row["note"],
            time=row["time"],
            energy=row["energy"],
            schedule=row["schedule"],
            contact_id=row["contact_id"].hex() if row["contact_id"] else None,
            tags=self._tags_by_item.get(item_id, []),
        )

    def _resolve_id(self, hex_id: str) -> bytes | None:
        """Resolve a full or prefix hex ID to a BLOB. Returns None if not found."""
        if len(hex_id) >= 32:
            try:
                return bytes.fromhex(hex_id)
            except ValueError:
                return None
        cur = self._conn.cursor()
        rows = cur.execute(
            "SELECT id FROM item WHERE hex(id) LIKE ?",
            (hex_id.upper() + "%",),
        ).fetchall()
        if len(rows) == 1:
            return rows[0]["id"]
        return None

    def _query_items(
        self,
        where: str = "1=1",
        params: tuple = (),
        order_by: str = "created_on DESC",
        limit: int | None = None,
    ) -> list[Item]:
        sql = (
            "SELECT id, title, note, type, list, created_on, completed_on, "
            "is_focused, due_date, start_date, parent_id, time, energy, "
            "schedule, contact_id "
            f"FROM item WHERE {where} ORDER BY {order_by}"
        )
        if limit is not None:
            sql += f" LIMIT {limit}"
        cur = self._conn.cursor()
        return [self._row_to_item(row) for row in cur.execute(sql, params)]

    def done(self, project_id: str | None = None, limit: int = 50) -> list[Item]:
        if project_id:
            blob = self._resolve_id(project_id)
            if blob is None:
                return []
            return self._query_items(
                "type = ? AND completed_on IS NOT NULL AND parent_id = ?",
                (ItemType.ACTION.value, blob),
                order_by="completed_on DESC",
                limit=limit,
            )
        return self._query_items(
            "type = ? AND completed_on IS NOT NULL",
            (ItemType.ACTION.value,),
            order_by="completed_on DESC",
            limit=limit,
        )

    def inbox(self) -> list[Item]:
        return self._query_items(
            "list = ? AND completed_on IS NULL",
            (ListType.INBOX.value,),
        )

    def active_projects(self) -> list[Item]:
        return self._query_items(
            "type = ? AND list = ? AND completed_on IS NULL",
            (ItemType.PROJECT.value, ListType.ACTIVE.value),
            order_by="title ASC",
        )

    def next_actions(self, project_id: str | None = None) -> list[Item]:
        if project_id:
            blob = self._resolve_id(project_id)
            if blob is None:
                return []
            return self._query_items(
                "type = ? AND list = ? AND completed_on IS NULL AND parent_id = ?",
                (ItemType.ACTION.value, ListType.ACTIVE.value, blob),
            )
        return self._query_items(
            "type = ? AND list = ? AND completed_on IS NULL",
            (ItemType.ACTION.value, ListType.ACTIVE.value),
        )

    def waiting(self) -> list[Item]:
        return self._query_items(
            "list = ? AND completed_on IS NULL",
            (ListType.WAITING.value,),
        )

    def scheduled(self) -> list[Item]:
        return self._query_items(
            "list = ? AND completed_on IS NULL",
            (ListType.SCHEDULED.value,),
            order_by="start_date ASC",
        )

    def someday_maybe(self) -> list[Item]:
        return self._query_items(
            "list = ? AND completed_on IS NULL",
            (ListType.SOMEDAY.value,),
        )

    def focused(self) -> list[Item]:
        return self._query_items(
            "is_focused = 1 AND completed_on IS NULL",
        )

    def notebooks(self) -> list[Item]:
        return self._query_items(
            "type = ? AND list = ?",
            (ItemType.NOTEBOOK.value, ListType.ACTIVE.value),
            order_by="title ASC",
        )

    def find_notebooks(self, query: str) -> list[Item]:
        """Find notebooks by hex ID prefix or case-insensitive name substring."""
        try:
            bytes.fromhex(query)
            is_hex = True
        except ValueError:
            is_hex = False
        if is_hex:
            items = self._query_items(
                "type = ? AND hex(id) LIKE ?",
                (ItemType.NOTEBOOK.value, query.upper() + "%"),
            )
            if items:
                return items
        return self._query_items(
            "type = ? AND title LIKE ?",
            (ItemType.NOTEBOOK.value, f"%{query}%"),
        )

    def notes(self, notebook_id: str | None = None) -> list[Item]:
        if notebook_id:
            blob = self._resolve_id(notebook_id)
            if blob is None:
                return []
            return self._query_items(
                "type = ? AND list = ? AND parent_id = ?",
                (ItemType.NOTE.value, ListType.ACTIVE.value, blob),
                order_by="title ASC",
            )
        return self._query_items(
            "type = ? AND list = ?",
            (ItemType.NOTE.value, ListType.ACTIVE.value),
            order_by="title ASC",
        )

    def project_tasks(self, project_id: str) -> list[Item]:
        blob = self._resolve_id(project_id)
        if blob is None:
            return []
        return self._query_items(
            "type = ? AND parent_id = ?",
            (ItemType.ACTION.value, blob),
            order_by="completed_on IS NOT NULL, position_child ASC",
        )

    def tags(self, tag_type: TagType | None = None) -> list[Tag]:
        all_tags = sorted(self._tags_by_id.values(), key=lambda t: t.title)
        if tag_type:
            return [t for t in all_tags if t.type == tag_type]
        return all_tags

    def search(self, query: str) -> list[Item]:
        return self._query_items(
            "title LIKE ? AND completed_on IS NULL",
            (f"%{query}%",),
        )

    def get_item(self, item_id: str) -> Item | None:
        if len(item_id) < 32:
            blob_prefix = bytes.fromhex(item_id)
            items = self._query_items(
                "hex(id) LIKE ?",
                (item_id.upper() + "%",),
            )
            return items[0] if items else None
        try:
            blob = bytes.fromhex(item_id)
        except ValueError:
            return None
        items = self._query_items("id = ?", (blob,))
        return items[0] if items else None

    def find_projects(self, query: str) -> list[Item]:
        """Find projects by hex ID prefix or case-insensitive name substring."""
        # Try hex ID prefix first
        try:
            bytes.fromhex(query)
            is_hex = True
        except ValueError:
            is_hex = False
        if is_hex:
            items = self._query_items(
                "type = ? AND hex(id) LIKE ?",
                (ItemType.PROJECT.value, query.upper() + "%"),
            )
            if items:
                return items
        # Fall back to case-insensitive title match
        return self._query_items(
            "type = ? AND title LIKE ?",
            (ItemType.PROJECT.value, f"%{query}%"),
        )

    def project_titles(self) -> dict[str, str]:
        """Return a mapping of project hex ID to project title."""
        cur = self._conn.cursor()
        rows = cur.execute(
            "SELECT id, title FROM item WHERE type = ?",
            (ItemType.PROJECT.value,),
        ).fetchall()
        return {row["id"].hex(): row["title"] for row in rows}

    def project_summary(self) -> list[tuple[Item, int, int]]:
        projects = self.active_projects()
        result = []
        for proj in projects:
            blob = bytes.fromhex(proj.id)
            cur = self._conn.cursor()
            row = cur.execute(
                "SELECT "
                "SUM(CASE WHEN completed_on IS NULL THEN 1 ELSE 0 END) AS open_count, "
                "SUM(CASE WHEN completed_on IS NOT NULL THEN 1 ELSE 0 END) AS done_count "
                "FROM item WHERE type = ? AND parent_id = ?",
                (ItemType.ACTION.value, blob),
            ).fetchone()
            result.append((proj, row["open_count"] or 0, row["done_count"] or 0))
        return result

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> EverdoDB:
        return self

    def __exit__(self, *exc) -> None:
        self.close()
