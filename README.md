# Everdo Library / Command Line Interface

A zero-dependency Python interface to the [Everdo](https://everdo.net/) GTD database: run read-only local queries,
or create inbox items through Everdo's API. Query your actions, projects, and tags from the command line or from
Python.

I am not affiliated with the Everdo project and this is not _the_ official library or CL tool. I just needed one.

## Features

- **Safe local queries**: opens the database in SQLite read-only mode; local queries never modify your data
- **Inbox capture**: create an Everdo inbox item through the API with a title, optional note, and optional focus flag
- **GTD views**: inbox, next actions, projects, waiting, scheduled, someday/maybe, focused
- **Project drill-down**: view a project's detail and its open/completed tasks
- **Cross-project task lists**: merge the tasks of several projects (archived ones included), with optional dedup
- **Notebooks & notes**: browse reference material
- **Prefix ID lookup**: refer to items by the first few characters of their hex ID
- **Tag support**: list and filter by areas, contacts, and labels
- **Title search**: case-insensitive substring search across item titles; multiple OR-combined terms, optionally including completed/archived items (`-a`)
- **Checklist compilation**: `search -a -t` prints deduplicated bare titles from current and past tasks — ideal for rebuilding recurring todo lists (e.g. a yearly trip) from what you did last time
- **Context manager API**: use `EverdoDB` in a `with` block for clean resource handling

## Installation

There is no pip package yet. Clone the repository and set your `PYTHONPATH`:

```bash
git clone https://github.com/larsborn/everdo everdo
cd everdo
export PYTHONPATH=src  # or SET under Windows
```

Then run with:

```bash
python3 -m everdo <command>
```

## CLI Usage

```
usage: everdo [-h] [--db DB]
               {inbox,inbox-add,next,done,projects,project,tasks,waiting,scheduled,
                someday,focused,notebooks,notes,tags,show,search} ...

CLI for Everdo GTD database and API inbox capture

positional arguments:
  {inbox,inbox-add,next,done,...}
    inbox               Show unprocessed inbox items
    inbox-add           Create an inbox item through the Everdo API
    next                Active next actions
    done                Completed tasks
    projects            List active projects with task counts
    project             Show project detail and its tasks
    tasks               List all tasks (open and completed) of one or more projects
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
$ python3 -m everdo inbox

Inbox
-----
ID         Title
------------------------------------------
a1b2c3d4   Buy groceries for the week
e5f6a7b8   Read article on time management
19d0c3e2   Schedule dentist appointment
```

### Projects

```
$ python3 -m everdo projects

ID         Project                             Created     Open  Done
----------------------------------------------------------------------
7d4e9f01   Q1 planning                         2026-01-05     3     8
3f8a1b2c   Home renovation                     2025-02-11    12     5
b2c5d8e3   Learn Spanish                       2024-08-30     6     2
```

Output is sorted by creation date, newest first. `--sort {created,title,open,done}` selects
another column (`title` sorts ascending, the rest descending) and `--reverse` flips the order:

```
$ python3 -m everdo projects --sort title
$ python3 -m everdo projects --sort open --reverse
```

By default only open, active projects are shown. Use `--list` to see other lists — including
completed projects — e.g. archived ones, or `all` for every project:

```
$ python3 -m everdo projects --list archived
$ python3 -m everdo projects --list all
```

(Choices: `all`, `inbox`, `active`, `scheduled`, `waiting`, `someday`, `deleted`, `archived`.)

`--filter` narrows the result to projects whose title contains a substring (case-insensitive),
which pairs well with `--list all` to find past years' projects:

```
$ python3 -m everdo projects --list all --filter Packliste
```

### Tasks across projects

`tasks` lists every task — open and completed — of one or more projects, archived projects
included. Each argument is an ID prefix or name substring, and *every* matching project is
included, so a single query like `Trip` can cover all years at once:

```
$ python3 -m everdo tasks "Trip 2024" "Trip 2025"
$ python3 -m everdo tasks Trip -t -p
```

The `-t`/`-p` flags work exactly like in `search`: `-t` prints deduplicated bare titles, and
`-t -p` renders the checkmark table — the quickest way to turn past years' project task lists
into a fresh checklist.

### Next Actions

```
$ python3 -m everdo next

Next Actions
------------
ID         Title                           Tags       Due
------------------------------------------------------------
3f8a1b2c   Pick paint colors               @home
7d4e9f01 * Draft budget proposal           @work      2026-03-20
b2c5d8e3   Practice vocabulary flashcards  @learning
```

Filter by project (ID prefix or name):

```
$ python3 -m everdo next --project 3f8a
$ python3 -m everdo next --project renovation

Next Actions
------------
ID         Title                Tags
---------------------------------------
3f8a1b2c   Pick paint colors    @home
3f8a9c01   Measure living room  @home
```

### Show Item Detail

```
$ python3 -m everdo show 7d4e

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
$ python3 -m everdo search budget

Search: budget
--------------
ID         Title                     Tags   Due
--------------------------------------------------
7d4e9f01 * Draft budget proposal     @work  2026-03-20
c4d5e6f7   Review department budget  @work
```

Multiple terms are OR-combined, and `-a/--all` includes completed and archived tasks:

```
$ python3 -m everdo search -a budget expenses

Search: budget, expenses
------------------------
  7d4e9f01 *  Draft budget proposal     @work  due:2026-03-20
  c4d5e6f7    Review department budget  @work
  91b0e4a2    Submit expenses Q3        @work
```

### Compiling a checklist from past tasks

To rebuild a recurring todo list (e.g. a yearly trip) from everything you did before, search across
all items — including completed ones — and print deduplicated bare titles with `-t/--titles`:

```
$ python3 -m everdo search -a -t packing sunscreen tent visa > trip-checklist.txt
```

Titles are deduplicated case-insensitively and alphabetized, one per line, without IDs or
truncation, so the output is easy to edit and to re-enter in Everdo manually. The local query commands are
read-only; `inbox-add` is the explicit API write path.

Add `-p` to see which project(s) each task came from — the output becomes an aligned table, and
duplicates merged across years list all their sources, which highlights the tasks that recur every
trip. A leading checkmark means no open instance of that task exists (every match is completed);
no checkmark means an open task with that title is already on one of your lists:

```
$ python3 -m everdo search -a -t -p packing tent visa

   Task                 Project(s)
--------------------------------------------
✓  Book campsite        Trip 2025
   Pack tent            Trip 2024, Trip 2025
✓  Renew visa           Trip 2024, Trip 2025
```

### Tags

```
$ python3 -m everdo tags --type area

Areas
--------------------
  1a2b3c4d  Home
  5e6f7a8b  Work
```

### Done

```
$ python3 -m everdo done -n 5

Done
----
ID         Title                  Tags
------------------------------------------
3f8a1b2c   Sand kitchen cabinets  @home
7d4e9f01   Submit expense report  @work
b2c5d8e3   Review chapter 3       @learning
```

Filter by project and/or limit results:

```
$ python3 -m everdo done --project renovation -n 10
```

### Other Commands

- `waiting`: items delegated or waiting on someone else
- `scheduled`: items with a future start date, sorted chronologically
- `someday`: someday/maybe items for later review
- `focused`: starred/focused items across all lists
- `notebooks`: reference notebooks
- `notes`: reference notes (use `--notebook <id or name>` to filter)

### Adding Inbox Items through the Everdo API

Enable the API in Everdo under **Settings -> API**, then restart Everdo. The default API URL is
`https://localhost:11111`.

`inbox-add` requires an API key. Supply it with `--api-key` or the `EVERDO_API_KEY` environment variable; the
command-line flag takes precedence. Likewise, `--api-url` overrides `EVERDO_API_URL`, which overrides the default
URL. Environment variables are preferable for the key because command-line arguments can be retained in shell
history.

```bash
python3 -m everdo inbox-add "Call the dentist" --api-key "$EVERDO_API_KEY"
python3 -m everdo inbox-add "Plan weekend trip" --note "Check trains and hotels" --api-key "$EVERDO_API_KEY"
python3 -m everdo inbox-add "Review proposal" --focused --api-key "$EVERDO_API_KEY"
```

You can keep both settings in the environment and omit them from the command line:

```bash
export EVERDO_API_URL=https://localhost:11111
export EVERDO_API_KEY=your-api-key
python3 -m everdo inbox-add "Capture meeting follow-up" --note "Send the recap" --focused
```

The command accepts a required title and these optional flags:

- `--note TEXT`: add a note to the new inbox item
- `--focused`: mark the item as focused
- `--api-url URL`: override `EVERDO_API_URL` and the default URL
- `--api-key KEY`: override `EVERDO_API_KEY` (required if the environment variable is unset)

Everdo requires the API key as a query parameter on the API request. Prefer `EVERDO_API_KEY` over `--api-key` so
the key is not exposed in command-line history. The URL precedence is `--api-url`, then `EVERDO_API_URL`, then the
default; the key precedence is `--api-key`, then `EVERDO_API_KEY`.

Requests use a fixed 30-second timeout. Everdo's local HTTPS endpoint commonly uses a self-signed certificate, so
certificate verification is intentionally disabled for this command. Use it only with a trusted Everdo instance and
trusted local network. On success, the command prints the created item ID and its UTC creation time.

### Global Options

Use `--db PATH` to point at a different database file:

```bash
python3 -m everdo --db /path/to/other/db inbox
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
| `time`         | `int \| None`      | Time estimate in minutes           |
| `energy`       | `int \| None`      | Energy level (1=low .. 3=high)     |
| `schedule`     | `str \| None`      | Recurrence schedule                |
| `contact_id`   | `str \| None`      | Waiting-for contact ID             |
| `tags`         | `list[Tag]`        | Attached tags                      |

Computed properties: `short_id` (first 8 hex chars), `is_complete`, `is_recurring`, `has_parent`.

### Tag dataclass

| Field   | Type          | Description             |
|---------|---------------|-------------------------|
| `id`    | `str`         | 32-char hex string      |
| `title` | `str`         | Tag name                |
| `type`  | `TagType`     | Area, contact, or label |
| `color` | `int \| None` | Display color           |

## Testing

The test suite uses `unittest` with a deterministic fixture database:

```bash
cd everdo
PYTHONPATH=src python -m unittest discover -s tests
```

All tests should pass. The fixture database is created fresh by `tests/conftest.py` for each test run.

## How It Works

Everdo stores its data in a SQLite database at `%APPDATA%\Everdo\db` on Windows. The local query path opens that
database in read-only mode (`?mode=ro` URI parameter), queries items, projects, tags, and their relationships, and
presents them through either the CLI or the Python API; it does not write to the database. The `inbox-add` path is
separate and does not open SQLite: it sends a JSON `POST` request to `/api/items/` with the API key and requested
fields, then validates the returned item ID and creation time. Both paths use only Python's standard library,
including `sqlite3` for local queries and `urllib`/`json` for the API request. IDs are stored as 16-byte BLOBs in
SQLite and exposed as 32-character hex strings. Timestamps are stored as seconds since epoch and converted to UTC
`datetime` objects.
