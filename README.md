# Everdo Library / Command Line Interface

A read-only zero-dependency Python interface to the [Everdo](https://everdo.net/) GTD database. Query your actions,
projects, and tags from the command line or from Python.

I am not affiliated with the Everdo project and this is not _the_ official library or CL tool. I just needed one.

## Features

- **Read-only & safe**: opens the database in SQLite read-only mode; your data is never modified
- **GTD views**: inbox, next actions, projects, waiting, scheduled, someday/maybe, focused
- **Project drill-down**: view a project's detail and its open/completed tasks
- **Notebooks & notes**: browse reference material
- **Prefix ID lookup**: refer to items by the first few characters of their hex ID
- **Tag support**: list and filter by areas, contacts, and labels
- **Full-text search**: case-insensitive search across item titles
- **Context manager API**: use `EverdoDB` in a `with` block for clean resource handling

## Installation

There is no pip package yet. Clone the repository and set your `PYTHONPATH`:

```bash
git clone https://gitihub.com/larsborn/everdo everdo
cd everdo
export PYTHONPATH=src  # or SET under Windows
```

Then run with:

```bash
python -m everdo <command>
```

## CLI Usage

```
usage: everdo [-h] [--db DB]
              {inbox,next,done,projects,project,waiting,scheduled,someday,
               focused,notebooks,notes,tags,show,search} ...

Read-only CLI for Everdo GTD database

positional arguments:
  {inbox,next,done,...}
    inbox               Show unprocessed inbox items
    next                Active next actions
    done                Completed tasks
    projects            List active projects with task counts
    project             Show project detail and its tasks
    waiting             Items waiting for someone
    scheduled           Scheduled items
    someday             Someday/Maybe items
    focused             Focused items
    notebooks           Reference notebooks
    notes               Reference notes
    tags                List tags
    show                Show detail view of any item
    search              Search item titles

options:
  -h, --help            show this help message and exit
  --db DB               Path to Everdo database (default: %APPDATA%\Everdo\db)
```

### Inbox

```
$ python -m everdo inbox

Inbox
-----
  a1b2c3d4    Buy groceries for the week
  e5f6a7b8    Read article on time management
  19d0c3e2    Schedule dentist appointment
```

### Projects

```
$ python -m everdo projects

ID         Project                                        Open  Done
-------------------------------------------------------------------
3f8a1b2c   Home renovation                                  12     5
7d4e9f01   Q1 planning                                       3     8
b2c5d8e3   Learn Spanish                                     6     2
```

### Next Actions

```
$ python -m everdo next

Next Actions
------------
  3f8a1b2c    Pick paint colors                @home
  7d4e9f01 *  Draft budget proposal             @work  due:2026-03-20
  b2c5d8e3    Practice vocabulary flashcards    @learning
```

Filter by project (ID prefix or name):

```
$ python -m everdo next --project 3f8a

Next Actions
------------
  3f8a1b2c    Pick paint colors    @home
  3f8a9c01    Measure living room  @home
```

```
$ python -m everdo next --project renovation

Next Actions
------------
  3f8a1b2c    Pick paint colors    @home
  3f8a9c01    Measure living room  @home
```

### Show Item Detail

```
$ python -m everdo show 7d4e

Title:       Draft budget proposal
ID:          7d4e9f01a2b3c4d5e6f7a8b9c0d1e2f3
Type:        ACTION
List:        ACTIVE
Focused:     yes
Due:         2026-03-20
Energy:      high
Time:        1h30m
Tags:        @work @planning
```

### Search

```
$ python -m everdo search budget

Search: budget
--------------
  7d4e9f01 *  Draft budget proposal    @work  due:2026-03-20
  c4d5e6f7    Review department budget  @work
```

### Tags

```
$ python -m everdo tags --type area

Areas
--------------------
  1a2b3c4d  Home
  5e6f7a8b  Work
```

### Done

```
$ python -m everdo done -n 5

Done
----
  3f8a1b2c    Sand kitchen cabinets    @home
  7d4e9f01    Submit expense report    @work
  b2c5d8e3    Review chapter 3         @learning
```

Filter by project and/or limit results:

```
$ python -m everdo done --project renovation -n 10
```

### Other Commands

- `waiting`: items delegated or waiting on someone else
- `scheduled`: items with a future start date, sorted chronologically
- `someday`: someday/maybe items for later review
- `focused`: starred/focused items across all lists
- `notebooks`: reference notebooks
- `notes`: reference notes (use `--notebook <id or name>` to filter)

### Global Options

Use `--db PATH` to point at a different database file:

```bash
python -m everdo --db /path/to/other/db inbox
```

## Python Library Usage

```python
from everdo.db import EverdoDB
from everdo.model import TagType

# Open the database (uses default path if none given)
with EverdoDB() as db:
    # List inbox items
    for item in db.inbox():
        print(f"{item.short_id}  {item.title}")

    # Active projects with task counts
    for proj, open_count, done_count in db.project_summary():
        print(f"{proj.title}: {open_count} open, {done_count} done")

    # Get a specific item by prefix ID
    item = db.get_item("7d4e")
    if item:
        print(f"{item.title} (due: {item.due_date})")

    # Filter tags by type
    areas = db.tags(TagType.AREA)
    for tag in areas:
        print(f"@{tag.title}")

    # Search items by title
    results = db.search("budget")
    for item in results:
        print(item.title)
```

You can also provide an explicit database path:

```python
with EverdoDB("/path/to/db") as db:
    print(len(db.inbox()), "items in inbox")
```

## Data Model

### Enums

| Enum       | Values                                                                      | Description                        |
|------------|-----------------------------------------------------------------------------|------------------------------------|
| `ItemType` | `ACTION`, `PROJECT`, `NOTEBOOK`, `NOTE`                                     | Kind of item                       |
| `ListType` | `INBOX`, `ACTIVE`, `SCHEDULED`, `WAITING`, `SOMEDAY`, `DELETED`, `ARCHIVED` | Which GTD list the item belongs to |
| `TagType`  | `AREA`, `CONTACT`, `LABEL`                                                  | Tag category                       |
| `Energy`   | `LOW` (1), `MEDIUM` (2), `HIGH` (3)                                         | Energy level required              |

### Item dataclass

| Field          | Type               | Description                        |
|----------------|--------------------|------------------------------------|
| `id`           | `str`              | 32-char hex string                 |
| `title`        | `str`              | Item title                         |
| `type`         | `ItemType`         | Action, project, notebook, or note |
| `list_type`    | `ListType`         | GTD list                           |
| `created_on`   | `datetime \| None` | Creation timestamp (UTC)           |
| `completed_on` | `datetime \| None` | Completion timestamp (UTC)         |
| `is_focused`   | `bool`             | Whether the item is starred        |
| `due_date`     | `datetime \| None` | Due date                           |
| `start_date`   | `datetime \| None` | Scheduled start date               |
| `parent_id`    | `str \| None`      | Parent project/notebook ID         |
| `note`         | `str \| None`      | Markdown note body                 |
| `tags`         | `list[Tag]`        | Attached tags                      |

Computed properties: `short_id` (first 8 hex chars), `is_complete`, `is_recurring`, `has_parent`.

### Tag dataclass

| Field   | Type      | Description             |
|---------|-----------|-------------------------|
| `id`    | `str`     | 32-char hex string      |
| `title` | `str`     | Tag name                |
| `type`  | `TagType` | Area, contact, or label |

## Testing

The test suite uses `unittest` with a deterministic fixture database:

```bash
cd everdo
PYTHONPATH=src python -m unittest discover -s tests
```

All tests should pass. The fixture database is created fresh by `tests/conftest.py` for each test run.

## How It Works

Everdo stores its data in a SQLite database at `%APPDATA%\Everdo\db` on Windows. This tool opens that database in
read-only mode (`?mode=ro` URI parameter), queries items, projects, tags, and their relationships, and presents them
through either the CLI or the Python API. IDs are stored as 16-byte BLOBs in SQLite and exposed as 32-character hex
strings. Timestamps are stored as seconds since epoch and converted to UTC `datetime` objects.
