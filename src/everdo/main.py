#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import sys

from everdo.db import EverdoDB, default_db_path
from everdo.formatting import (
    print_item_detail,
    print_items,
    print_project_summary,
    print_tags,
)
from everdo.model import TagType


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="everdo", description="Read-only CLI for Everdo GTD database"
    )
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

    next_p = sub.add_parser("next", help="Active next actions")
    next_p.add_argument(
        "--project", default=None, help="Filter by project ID prefix or name"
    )
    _add_list_flags(next_p)

    done_p = sub.add_parser("done", help="Completed tasks")
    done_p.add_argument(
        "--project", default=None, help="Filter by project ID prefix or name"
    )
    done_p.add_argument(
        "-n", "--limit", type=int, default=50, help="Max items to show (default: 50)"
    )
    _add_list_flags(done_p)
    done_p.add_argument(
        "-d",
        "--show-completed",
        action="store_true",
        help="Show completion date for each item",
    )

    sub.add_parser("projects", help="List active projects with task counts")

    proj_p = sub.add_parser("project", help="Show project detail and its tasks")
    proj_p.add_argument("id", help="Project hex ID (or prefix)")

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
    notes_p.add_argument(
        "--notebook", default=None, help="Filter by notebook ID prefix or name"
    )
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
    search_p.add_argument("query", help="Search string (case-insensitive)")
    _add_list_flags(search_p)

    return parser


def main(argv: list[str] | None = None) -> None:
    sys.stdout.reconfigure(
        errors="replace"
    )  # avoid problems with emojis in some terminals
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    with EverdoDB(args.db) as db:
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
            _print(db.done(project_id, args.limit), "Done")

        elif args.command == "projects":
            print_project_summary(db.project_summary())

        elif args.command == "project":
            proj = db.get_item(args.id)
            if not proj:
                print(f"Project not found: {args.id}", file=sys.stderr)
                sys.exit(1)
            print_item_detail(proj)
            _print(db.project_tasks(proj.id), "Tasks")

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
                    print(
                        f"No notebook found matching: {args.notebook}", file=sys.stderr
                    )
                    sys.exit(1)
                if len(matches) > 1:
                    print(
                        f"Multiple notebooks match '{args.notebook}':", file=sys.stderr
                    )
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
            _print(db.search(args.query), f"Search: {args.query}")


if __name__ == "__main__":
    main()
