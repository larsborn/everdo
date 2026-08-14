#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import timezone

from everdo.api import DEFAULT_API_URL, EverdoAPI, EverdoAPIError
from everdo.db import EverdoDB, default_db_path
from everdo.formatting import (
    print_item_detail,
    print_items,
    print_project_summary,
    print_tags,
    print_titles,
)
from everdo.model import ItemType, ListType, TagType


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="everdo", description="Read-only CLI for Everdo GTD database")
    parser.add_argument(
        "--db",
        default=None,
        help=f"Path to Everdo database (default: {default_db_path()})",
    )
    sub = parser.add_subparsers(dest="command")

    _show_proj_help = "Show parent project name for each item"
    _show_created_help = "Show creation date for each item"

    def _add_list_flags(p: argparse.ArgumentParser, *, project: bool = True) -> None:
        if project:
            p.add_argument("-p", "--show-project", action="store_true", help=_show_proj_help)
        p.add_argument("-c", "--show-created", action="store_true", help=_show_created_help)
        p.add_argument("--count", action="store_true", help="Print item count instead of the full list")

    inbox_p = sub.add_parser("inbox", help="Show unprocessed inbox items")
    _add_list_flags(inbox_p, project=False)

    inbox_add_p = sub.add_parser("inbox-add", help="Create an inbox item through the Everdo API")
    inbox_add_p.add_argument("title", help="Title of the new inbox item")
    inbox_add_p.add_argument("--note", default=None, help="Optional note for the new item")
    inbox_add_p.add_argument("--focused", action="store_true", help="Mark the new item as focused")
    inbox_add_p.add_argument("--api-url", default=None, help="Everdo API URL")
    inbox_add_p.add_argument("--api-key", default=None, help="Everdo API key")

    next_p = sub.add_parser("next", help="Active next actions")
    next_p.add_argument("--project", default=None, help="Filter by project ID prefix or name")
    _add_list_flags(next_p)

    done_p = sub.add_parser("done", help="Completed tasks")
    done_p.add_argument("--project", default=None, help="Filter by project ID prefix or name")
    done_p.add_argument("-n", "--limit", type=int, default=50, help="Max items to show (default: 50)")
    _add_list_flags(done_p)
    done_p.add_argument(
        "-d",
        "--show-completed",
        action="store_true",
        help="Show completion date for each item",
    )

    projects_p = sub.add_parser("projects", help="List active projects with task counts")
    projects_p.add_argument(
        "--list",
        dest="list_filter",
        choices=["all", "inbox", "active", "scheduled", "waiting", "someday", "deleted", "archived"],
        default=None,
        help="Show projects from this list instead of only open active ones "
        "('all' for every list); includes completed projects",
    )
    projects_p.add_argument(
        "--filter",
        dest="title_filter",
        default=None,
        help="Only show projects whose title contains this substring (case-insensitive)",
    )
    projects_p.add_argument(
        "--sort",
        choices=["created", "title", "open", "done"],
        default="created",
        help="Sort column; created/open/done sort descending, title ascending (default: created)",
    )
    projects_p.add_argument("--reverse", action="store_true", help="Reverse the sort order")

    proj_p = sub.add_parser("project", help="Show project detail and its tasks")
    proj_p.add_argument("id", help="Project hex ID (or prefix)")

    tasks_p = sub.add_parser("tasks", help="List all tasks (open and completed) of one or more projects")
    tasks_p.add_argument(
        "project",
        nargs="+",
        help="Project ID prefix or name; every matching project is included",
    )
    tasks_p.add_argument(
        "-t",
        "--titles",
        action="store_true",
        help="Print deduplicated bare titles only, for compiling checklists",
    )
    tasks_p.add_argument(
        "-d",
        "--show-completed",
        action="store_true",
        help="Show completion date for each item",
    )
    _add_list_flags(tasks_p)

    waiting_p = sub.add_parser("waiting", help="Items waiting for someone")
    _add_list_flags(waiting_p)

    scheduled_p = sub.add_parser("scheduled", help="Scheduled items")
    _add_list_flags(scheduled_p)

    someday_p = sub.add_parser("someday", help="Someday/Maybe items")
    _add_list_flags(someday_p)

    focused_p = sub.add_parser("focused", help="Focused items")
    _add_list_flags(focused_p)

    notebooks_p = sub.add_parser("notebooks", help="Reference notebooks")
    _add_list_flags(notebooks_p, project=False)

    notes_p = sub.add_parser("notes", help="Reference notes")
    notes_p.add_argument("--notebook", default=None, help="Filter by notebook ID prefix or name")
    _add_list_flags(notes_p, project=False)

    tags_p = sub.add_parser("tags", help="List tags")
    tags_p.add_argument(
        "--type",
        choices=["area", "contact", "label"],
        default=None,
        help="Filter by tag type",
    )

    show_p = sub.add_parser("show", help="Show detail view of any item")
    show_p.add_argument("id", help="Item hex ID (or prefix)")

    search_p = sub.add_parser("search", help="Search item titles")
    search_p.add_argument(
        "query",
        nargs="+",
        help="One or more search strings (case-insensitive, OR-combined)",
    )
    search_p.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="Include completed items (done and archived tasks)",
    )
    search_p.add_argument(
        "-t",
        "--titles",
        action="store_true",
        help="Print deduplicated bare titles only, for compiling checklists",
    )
    _add_list_flags(search_p)

    return parser


def main(argv: list[str] | None = None) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")  # avoid problems with emojis in some terminals
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "inbox-add":
        if args.api_url == "":
            print("Cannot create inbox item: API URL must not be empty", file=sys.stderr)
            sys.exit(1)
        api_url = args.api_url if args.api_url is not None else os.environ.get("EVERDO_API_URL") or DEFAULT_API_URL
        api_key = args.api_key if args.api_key is not None else os.environ.get("EVERDO_API_KEY")
        if not api_key:
            print("Cannot create inbox item: API key is required", file=sys.stderr)
            sys.exit(1)
        api = EverdoAPI(api_url, api_key)
        try:
            item = api.create_inbox_item(args.title, note=args.note, is_focused=args.focused)
        except EverdoAPIError as exc:
            print(f"Cannot create inbox item: {exc}", file=sys.stderr)
            sys.exit(1)
        created_on = item.created_on.astimezone(timezone.utc)
        print(f"{item.id}\t{created_on.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        return 0

    try:
        db = EverdoDB(args.db)
    except sqlite3.OperationalError as exc:
        print(f"Cannot open database at {args.db or default_db_path()}: {exc}", file=sys.stderr)
        sys.exit(1)

    with db:
        proj_names = None
        if getattr(args, "show_project", False):
            proj_names = db.project_titles()
        show_created = getattr(args, "show_created", False)
        show_completed = getattr(args, "show_completed", False)

        count_only = getattr(args, "count", False)

        def _print(items: list, title: str) -> None:
            if count_only:
                print(len(items))
                return
            print_items(
                items,
                title,
                proj_names,
                show_created=show_created,
                show_completed=show_completed,
            )

        if args.command == "inbox":
            _print(db.inbox(), "Inbox")

        elif args.command == "next":
            project_id = None
            if args.project:
                matches = db.find_projects(args.project)
                if not matches:
                    print(f"No project found matching: {args.project}", file=sys.stderr)
                    sys.exit(1)
                if len(matches) > 1:
                    print(f"Multiple projects match '{args.project}':", file=sys.stderr)
                    for m in matches:
                        print(f"  {m.short_id}  {m.title}", file=sys.stderr)
                    sys.exit(1)
                project_id = matches[0].id
            _print(db.next_actions(project_id), "Next Actions")

        elif args.command == "done":
            project_id = None
            if args.project:
                matches = db.find_projects(args.project)
                if not matches:
                    print(f"No project found matching: {args.project}", file=sys.stderr)
                    sys.exit(1)
                if len(matches) > 1:
                    print(f"Multiple projects match '{args.project}':", file=sys.stderr)
                    for m in matches:
                        print(f"  {m.short_id}  {m.title}", file=sys.stderr)
                    sys.exit(1)
                project_id = matches[0].id
            # --count must report the true total, not one capped by the display limit
            limit = None if count_only else args.limit
            _print(db.done(project_id, limit), "Done")

        elif args.command == "projects":
            if args.list_filter:
                list_type = None if args.list_filter == "all" else ListType[args.list_filter.upper()]
                projects = db.all_projects(list_type)
            else:
                projects = db.active_projects()
            if args.title_filter:
                needle = args.title_filter.lower()
                projects = [p for p in projects if needle in p.title.lower()]
            summaries = db.project_summary(projects)
            sort_keys = {
                "created": lambda s: s[0].created_on.timestamp() if s[0].created_on else 0,
                "title": lambda s: s[0].title.lower(),
                "open": lambda s: s[1],
                "done": lambda s: s[2],
            }
            descending = args.sort != "title"
            summaries.sort(key=sort_keys[args.sort], reverse=descending != args.reverse)
            print_project_summary(summaries)

        elif args.command == "project":
            proj = db.get_item(args.id)
            if not proj:
                print(f"Project not found: {args.id}", file=sys.stderr)
                sys.exit(1)
            if proj.type != ItemType.PROJECT:
                print(f"Not a project: {proj.short_id} ({proj.title})", file=sys.stderr)
                sys.exit(1)
            print_item_detail(proj)
            _print(db.project_tasks(proj.id), "Tasks")

        elif args.command == "tasks":
            projects_by_id = {}
            for query in args.project:
                matches = db.find_projects(query)
                if not matches:
                    print(f"No project found matching: {query}", file=sys.stderr)
                    sys.exit(1)
                for match in matches:
                    projects_by_id.setdefault(match.id, match)
            items = []
            seen_ids = set()
            for proj in projects_by_id.values():
                for item in db.project_tasks(proj.id):
                    if item.id not in seen_ids:
                        seen_ids.add(item.id)
                        items.append(item)
            if args.titles:
                print_titles(items, proj_names)
            else:
                _print(items, "Tasks")

        elif args.command == "waiting":
            _print(db.waiting(), "Waiting")

        elif args.command == "scheduled":
            _print(db.scheduled(), "Scheduled")

        elif args.command == "someday":
            _print(db.someday_maybe(), "Someday/Maybe")

        elif args.command == "focused":
            _print(db.focused(), "Focused")

        elif args.command == "notebooks":
            _print(db.notebooks(), "Notebooks")

        elif args.command == "notes":
            notebook_id = None
            if args.notebook:
                matches = db.find_notebooks(args.notebook)
                if not matches:
                    print(f"No notebook found matching: {args.notebook}", file=sys.stderr)
                    sys.exit(1)
                if len(matches) > 1:
                    print(f"Multiple notebooks match '{args.notebook}':", file=sys.stderr)
                    for m in matches:
                        print(f"  {m.short_id}  {m.title}", file=sys.stderr)
                    sys.exit(1)
                notebook_id = matches[0].id
            _print(db.notes(notebook_id), "Notes")

        elif args.command == "tags":
            tag_type = None
            if args.type:
                tag_type = TagType(args.type[0])
            print_tags(db.tags(tag_type))

        elif args.command == "show":
            item = db.get_item(args.id)
            if not item:
                print(f"Item not found: {args.id}", file=sys.stderr)
                sys.exit(1)
            print_item_detail(item)

        elif args.command == "search":
            by_id = {}
            for query in args.query:
                for item in db.search(query, include_done=args.all):
                    by_id.setdefault(item.id, item)
            items = sorted(
                by_id.values(),
                key=lambda i: i.created_on.timestamp() if i.created_on else 0,
                reverse=True,
            )
            if args.titles:
                print_titles(items, proj_names)
            else:
                _print(items, f"Search: {', '.join(args.query)}")


if __name__ == "__main__":
    main()
