# Read Things through AppleScript

The MCP runs the bundled `scripts/read_todos.applescript` with `/usr/bin/osascript`.
It requires no installed Shortcut or second server. macOS can ask for Automation
access to Things on the first read. Approve that access for the process shown in
the prompt. If access is denied, check System Settings → Privacy & Security →
Automation.

The native script has passed live checks for Today, creation-day filtering, and
a parent scope. The Python/MCP dispatch path and its output schema also passed.
The project now permits agent-run checks of this bundled read-only script and
its Python wrapper. Other host actions retain the earlier user-run boundary.

## Run the first check

Run this read-only check on your Mac. It requests the native Today
collection and returns the data through the same Python path used by the tool:

```sh
cd /Users/nicocarbone/dev/things-mcp
.venv/bin/python -B -c 'import asyncio; from reads import search; from read_models import SearchRequest, SearchScope; print(asyncio.run(search(SearchRequest(scope=SearchScope(list_name="Today")))).model_dump_json(indent=2))'
```

The error message includes AppleScript's error text if compilation, Automation
access, or a property read fails. For a direct check, run:

```sh
/usr/bin/osascript scripts/read_todos.applescript "Today" "" ""
```

The three script arguments are a native list name, a direct parent ID, and a
creation-day cutoff (`YYYY-MM-DD`). Empty strings mean no constraint. Use the
list name shown in Things if the app uses a language other than English.

After a successful check, restart the Codex MCP connection to load the changed
tool. Future reads run automatically with the MCP.

## Requests

The tool is `search_todos`, with a `payload` object. For native Today listing:

```json
{"payload": {"scope": {"list_name": "Today"}}}
```

For open items mentioning rent:

```json
{
  "payload": {
    "query": "rent",
    "filters": [{"field": "status", "operator": "equals", "value": "open"}],
    "match": "all"
  }
}
```

Optional scope constraints are:

| Field | Meaning |
| --- | --- |
| `list_name` | Read the native collection, in its displayed order. Examples: Today, Inbox, Logbook, Trash. |
| `parent_id` | Require a direct parent project or area ID. An area ID does not include items in its child projects. |
| `created_on_or_after` | Require creation on or after this local calendar day. |

If a list and parent are both supplied, AppleScript reads the list and Python
checks the parent constraint. Otherwise, AppleScript uses the parent collection
when supplied. The creation-day constraint is applied natively and checked again
in Python. All supplied scope constraints are required regardless of `match`.

The detailed filter models and their operators are unchanged. Text comparisons
ignore letter case. Dates compare calendar days; exported timestamps keep the
Mac's local UTC offset. Missing values do not satisfy comparisons. Empty groups
add no restriction. `query` is one condition in the all/any group and searches
title, notes, direct tag names, project names, and area names.

Canceled items are excluded unless a `status equals canceled` filter is supplied.
A completion Boolean of false matches only open items. Results are deduplicated
by ID without changing the first matching item's position.

## Available fields and limits

Core records include IDs, title, notes, individual tag names, status, all six
public date properties, and project/area names. Tags are read as objects rather
than split from a comma-separated string. JSON serialization handles quotes,
line breaks, and Unicode through Foundation.

`when_date` reports a known activation day only. When it is null, this reader
does not distinguish Anytime from Someday. Reminder time and evening state are
not available through this record. An activation day is not a substitute for
the full schedule value accepted by the add command.

Check `unavailable_fields` in every response. Checklist, heading, reminder,
evening, start state, Inbox flag, and logged flag are currently unknown. Their
record values are null, rather than an empty checklist or a false flag. Native
list selection is still available through `scope.list_name`; an explicit Inbox
or Logbook read does not require a per-record flag. Checklist and heading search
are deferred. The private experimental JSON property is not used.

There is no 500-item cap or output pagination in this backend.
`candidate_count` counts records before detailed Python filtering;
`possibly_truncated` is false because the reader does not impose a result cap.
The 30-second timeout produces a tool error and never returns a partial success.
On timeout or cancellation, the runner kills and reaps its CLI process.

Read failures also produce a tool error. No individual records are silently
skipped. The MCP validates the JSON and its record count before matching.
Other native collection coverage, including Trash, still needs live checks;
the code does not infer list membership from dates.

Sources: [Things AppleScript commands](https://culturedcode.com/things/support/articles/4562654/),
[AppleScript and Foundation](https://developer.apple.com/library/archive/documentation/LanguagesUtilities/Conceptual/MacAutomationScriptingGuide/AppendixA-AppleScriptObjCQuickTranslationGuide.html),
[Foundation JSON serialization](https://developer.apple.com/documentation/foundation/jsonserialization).
