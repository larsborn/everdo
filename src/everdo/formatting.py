#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import shutil
from datetime import datetime

from everdo.model import Energy, Item, Tag, TagType


def _terminal_width() -> int:
    return shutil.get_terminal_size(fallback=(80, 24)).columns - 1


def _clean(text: str) -> str:
    """Collapse all whitespace (including newlines) into single spaces for one-line output."""
    return " ".join(text.split())


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
    return " ".join(f"@{_clean(t.title)}" for t in tags)


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
    rows = []
    for item in items:
        project = ""
        if project_names and item.parent_id:
            project = _clean(project_names.get(item.parent_id, ""))
        rows.append(
            (
                item.short_id,
                "*" if item.is_focused else "",
                _clean(item.title),
                project,
                format_tags(item.tags),
                format_date(item.due_date),
                format_date(item.created_on) if show_created else "",
                format_date(item.completed_on) if show_completed else "",
            )
        )
    # optional columns appear only when at least one row has content for them;
    # Project sits in front of Title, the rest trail behind it
    has_project = any(row[3] for row in rows)
    proj_w = max(len("Project"), max(len(row[3]) for row in rows)) if has_project else 0
    tail = [
        (header, idx)
        for header, idx in [("Tags", 4), ("Due", 5), ("Created", 6), ("Done", 7)]
        if any(row[idx] for row in rows)
    ]
    tail_widths = [max(len(header), max(len(row[idx]) for row in rows)) for header, idx in tail]
    # columns: ID (8) + focus mark (1) + [Project] + Title (leftover) + tail, single-space separated
    fixed = 8 + 1 + 1 + 1 + (proj_w + 1 if has_project else 0) + sum(w + 1 for w in tail_widths)
    title_w = max(20, width - fixed)
    header_line = f"{'ID':<8} {'':<1}"
    if has_project:
        header_line += f" {'Project':<{proj_w}}"
    header_line += f" {'Title':<{title_w}}"
    for (header, _), w in zip(tail, tail_widths):
        header_line += f" {header:<{w}}"
    print(header_line.rstrip())
    print("-" * (fixed + title_w))
    for row in rows:
        line = f"{row[0]:<8} {row[1]:<1}"
        if has_project:
            line += f" {row[3]:<{proj_w}}"
        line += f" {_truncate(row[2], title_w):<{title_w}}"
        for (_, idx), w in zip(tail, tail_widths):
            line += f" {row[idx]:<{w}}"
        print(line.rstrip())


def dedupe_titles(
    items: list[Item],
    project_names: dict[str, str] | None = None,
) -> list[tuple[str, bool, list[str]]]:
    """Unique item titles (case-insensitive, whitespace-trimmed), alphabetized.

    Returns (title, done, source project names) triples; duplicates merged across
    projects aggregate all their sources. `done` is True only when every merged
    occurrence is completed — one open instance means the task is still pending.
    Keeps the first-seen spelling of each title, so pass items in preference
    order. Sources stay empty without project_names.
    """
    seen: dict[str, str] = {}
    done: dict[str, bool] = {}
    sources: dict[str, list[str]] = {}
    for item in items:
        title = _clean(item.title)
        key = title.lower()
        seen.setdefault(key, title)
        done[key] = done.get(key, True) and item.is_complete
        srcs = sources.setdefault(key, [])
        if project_names and item.parent_id:
            name = project_names.get(item.parent_id)
            if name:
                name = _clean(name)
                if name not in srcs:
                    srcs.append(name)
    return [(seen[key], done[key], sources[key]) for key in sorted(seen)]


def print_titles(items: list[Item], project_names: dict[str, str] | None = None) -> None:
    """Deduplicated titles — no IDs.

    Without project_names: bare untruncated titles, one per line, pipe-friendly.
    With project_names: an aligned table in the same style as the projects
    summary, with done-status and source-project columns.
    """
    rows = dedupe_titles(items, project_names)
    if project_names is None:
        for title, _, _ in rows:
            print(title)
        return
    width = _terminal_width()
    proj_cells = [", ".join(projects) for _, _, projects in rows]
    proj_w = max([len("Project(s)")] + [len(p) for p in proj_cells])
    # columns: done mark (2, no header — the checkmark speaks for itself)
    # + Task (leftover) + Project(s), single-space separated
    mark_w = 2
    task_w = max(20, width - mark_w - proj_w - 2)
    print(f"\n{'':<{mark_w}} {'Task':<{task_w}} Project(s)")
    print("-" * (mark_w + 1 + task_w + 1 + proj_w))
    if not rows:
        print("  (none)")
        return
    for (title, is_done, _), projects in zip(rows, proj_cells):
        mark = "✓" if is_done else ""
        print(f"{mark:<{mark_w}} {_truncate(title, task_w):<{task_w}} {projects}")


def print_project_summary(summaries: list[tuple[Item, int, int]]) -> None:
    width = _terminal_width()
    # columns: ID (10) + Created (10) + Open (5) + Done (5) + 4 separators = 34 fixed
    proj_width = max(20, width - 34)
    line_width = proj_width + 34
    print(f"\n{'ID':<10} {'Project':<{proj_width}} {'Created':<10} {'Open':>5} {'Done':>5}")
    print("-" * line_width)
    if not summaries:
        print("  (none)")
        return
    for proj, open_count, done_count in summaries:
        print(
            f"{proj.short_id:<10} {_truncate(_clean(proj.title), proj_width):<{proj_width}} "
            f"{format_date(proj.created_on):<10} {open_count:>5} {done_count:>5}"
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
    print(f"\n{'Title:':<12} {_clean(item.title)}")
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
