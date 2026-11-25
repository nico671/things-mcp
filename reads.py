import asyncio
import operator
from contextlib import suppress
from datetime import datetime
from pathlib import Path

from mcp.server.mcpserver.exceptions import ToolError
from pydantic import ValidationError

from read_models import (
    CompletionFilter,
    ContainerFilter,
    DateFilter,
    ReadBatch,
    SearchRequest,
    SearchResult,
    SearchScope,
    StatusFilter,
    TagFilter,
    TextFilter,
    TodoFilter,
    TodoRecord,
)

READ_SCRIPT = Path(__file__).resolve().parent / "scripts" / "read_todos.applescript"
READ_TIMEOUT_SECONDS = 30
DATE_OPERATORS = {
    "eq": operator.eq,
    "geq": operator.ge,
    "gt": operator.gt,
    "lt": operator.lt,
    "leq": operator.le,
}


async def read_candidates(scope: SearchScope) -> ReadBatch:
    """Read JSON from a bundled script; scope values are arguments, not code."""
    process = None
    try:
        process = await asyncio.create_subprocess_exec(
            "/usr/bin/osascript",
            str(READ_SCRIPT),
            scope.list_name or "",
            scope.parent_id or "",
            scope.created_on_or_after.isoformat() if scope.created_on_or_after else "",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        output, errors = await asyncio.wait_for(
            process.communicate(), timeout=READ_TIMEOUT_SECONDS
        )
        if process.returncode != 0:
            detail = errors.decode("utf-8", errors="replace").strip()[:1000]
            raise ToolError(
                f"AppleScript could not read Things (exit {process.returncode}): "
                f"{detail}. Check Automation access; see docs/applescript.md."
            )
        return ReadBatch.model_validate_json(output)
    except TimeoutError as exc:
        raise ToolError(
            "Timed out reading Things through AppleScript after 30 seconds."
        ) from exc
    except ValidationError as exc:
        raise ToolError(
            "AppleScript returned invalid JSON or item fields. "
            "See docs/applescript.md."
        ) from exc
    except OSError as exc:
        raise ToolError("Could not start the AppleScript reader.") from exc
    finally:
        if process is not None and process.returncode is None:
            with suppress(ProcessLookupError):
                process.kill()
            await process.communicate()


def matches_filter(item: TodoRecord, condition: TodoFilter) -> bool:
    """Evaluate one validated condition against a normalized record."""
    if isinstance(condition, (TextFilter, ContainerFilter)):
        value = getattr(item, condition.field)
        if value is None:
            return False
        value, expected = value.casefold(), condition.value.casefold()
        return (
            value == expected if condition.operator == "equals" else expected in value
        )
    if isinstance(condition, TagFilter):
        expected = condition.value.casefold()
        return any(
            tag.casefold() == expected if condition.operator == "equals"
            else expected in tag.casefold()
            for tag in item.tags
        )
    if isinstance(condition, StatusFilter):
        return item.status == condition.value
    if isinstance(condition, CompletionFilter):
        return item.status == ("completed" if condition.value else "open")
    if isinstance(condition, DateFilter):
        value = getattr(item, condition.field)
        if value is None:
            return False
        if isinstance(value, datetime):
            value = value.date()
        return DATE_OPERATORS[condition.operator](value, condition.value)
    raise TypeError(f"Unsupported filter model: {type(condition).__name__}")


def filter_candidates(batch: ReadBatch, request: SearchRequest) -> SearchResult:
    """Recheck scope, evaluate the full condition group, and deduplicate by ID."""
    include_canceled = any(
        isinstance(condition, StatusFilter) and condition.value == "canceled"
        for condition in request.filters
    )
    items = []
    seen = set()
    query = request.query.casefold() if request.query is not None else None
    for item in batch.items:
        if item.id in seen:
            continue
        if item.status == "canceled" and not include_canceled:
            continue
        if (request.scope.parent_id is not None
                and item.list_id != request.scope.parent_id):
            continue
        if (request.scope.created_on_or_after is not None
                and item.creation_date.date() < request.scope.created_on_or_after):
            continue

        conditions = [matches_filter(item, condition) for condition in request.filters]
        if query is not None:
            searchable = [
                item.title, item.notes, *item.tags, item.project, item.area,
            ]
            conditions.append(any(
                query in value.casefold() for value in searchable if value is not None
            ))
        if conditions and not (
            all(conditions) if request.match == "all" else any(conditions)
        ):
            continue
        items.append(item)
        seen.add(item.id)

    return SearchResult(
        items=items,
        candidate_count=batch.candidate_count,
    )


async def search(request: SearchRequest) -> SearchResult:
    return filter_candidates(await read_candidates(request.scope), request)
