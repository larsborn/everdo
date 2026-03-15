#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import shutil
from datetime import datetime

from everdo.model import Energy, Item, Tag, TagType


def _terminal_width() -> int:
    return shutil.get_terminal_size(fallback=(80, 24)).columns - 1


def _truncate(text: str, width: int) -> str:
    if len(text) <= width:
        return text
    if width <= 3:
        return text[:width]
    return text[: width - 3] + "..."


def format_date(dt: datetime | None) -> str:
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%d")


def format_tags(tags: list[Tag]) -> str:
    if not tags:
        return ""
    return " ".join(f"@{t.title}" for t in tags)


def format_energy(energy: int | None) -> str:
    if energy is None:
        return ""
    try:
        return Energy(energy).name.lower()
    except ValueError:
        return str(energy)


def format_time(minutes: int | None) -> str:
    if minutes is None:
        return ""
    if minutes < 60:
        return f"{minutes}m"
    h, m = divmod(minutes, 60)
    return f"{h}h{m}m" if m else f"{h}h"


def print_items(
    items: list[Item],
    title: str | None = None,
    project_names: dict[str, str] | None = None,
    show_created: bool = False,
    show_completed: bool = False,
) -> None:
    if title:
        print(f"\n{title}")
        print("-" * len(title))
    if not items:
        print("  (none)")
        return
    width = _terminal_width()
    # prefix: "  " + 8-char id + " " + focus + " " = 14 chars
    # reserve space for tags/due suffix (approx 30 chars)
    title_width = max(20, width - 44)
    for item in items:
        focused = "*" if item.is_focused else " "
        tags = format_tags(item.tags)
        due = format_date(item.due_date)
        parts = [f"  {item.short_id} {focused} {_truncate(item.title, title_width)}"]
        if project_names and item.parent_id:
            proj_name = project_names.get(item.parent_id)
            if proj_name:
                parts.append(f"[{proj_name}]")
        if tags:
            parts.append(tags)
        if due:
            parts.append(f"due:{due}")
        if show_created:
            created = format_date(item.created_on)
            if created:
                parts.append(f"created:{created}")
        if show_completed:
            completed = format_date(item.completed_on)
            if completed:
                parts.append(f"done:{completed}")
        print("  ".join(parts))


def print_project_summary(summaries: list[tuple[Item, int, int]]) -> None:
    width = _terminal_width()
    # columns: ID (10) + 3 spaces + Open (5) + Done (5) = 23 fixed
    proj_width = max(20, width - 23)
    line_width = proj_width + 23
    print(f"\n{'ID':<10} {'Project':<{proj_width}} {'Open':>5} {'Done':>5}")
    print("-" * line_width)
    if not summaries:
        print("  (none)")
        return
    for proj, open_count, done_count in summaries:
        print(
            f"{proj.short_id:<10} {_truncate(proj.title, proj_width):<{proj_width}} {open_count:>5} {done_count:>5}"
        )


def print_tags(tags: list[Tag]) -> None:
    by_type: dict[TagType, list[Tag]] = {}
    for tag in tags:
        by_type.setdefault(tag.type, []).append(tag)
    for tag_type in (TagType.AREA, TagType.CONTACT, TagType.LABEL):
        group = by_type.get(tag_type, [])
        if group:
            print(f"\n{tag_type.name.title()}s")
            print("-" * 20)
            for tag in group:
                print(f"  {tag.id[:8]}  {tag.title}")


def print_item_detail(item: Item) -> None:
    print(f"\n{'Title:':<12} {item.title}")
    print(f"{'ID:':<12} {item.id}")
    print(f"{'Type:':<12} {item.type.name}")
    print(f"{'List:':<12} {item.list_type.name}")
    if item.is_focused:
        print(f"{'Focused:':<12} yes")
    if item.completed_on:
        print(f"{'Completed:':<12} {format_date(item.completed_on)}")
    if item.due_date:
        print(f"{'Due:':<12} {format_date(item.due_date)}")
    if item.start_date:
        print(f"{'Start:':<12} {format_date(item.start_date)}")
    if item.energy is not None:
        print(f"{'Energy:':<12} {format_energy(item.energy)}")
    if item.time is not None:
        print(f"{'Time:':<12} {format_time(item.time)}")
    if item.schedule:
        print(f"{'Schedule:':<12} {item.schedule}")
    if item.tags:
        print(f"{'Tags:':<12} {format_tags(item.tags)}")
    if item.note:
        print(f"\n--- Note ---\n{item.note}")
