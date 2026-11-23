import asyncio
import secrets
from contextlib import suppress
from typing import Annotated
from urllib.parse import quote, urlencode

from mcp.server import MCPServer
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, Field

from callbacks import CallbackResult, CallbackState, callback_lifespan

mcp = MCPServer("things-mcp", lifespan=callback_lifespan)

THINGS_ADD_BASE_URL = "things:///add?"
CALLBACK_TIMEOUT_SECONDS = 30
OPEN_TIMEOUT_SECONDS = 5


class AddPayload(BaseModel):
    title: str = Field(description="The title of the to-do.")
    notes: str | None = Field(
        default=None,
        max_length=10_000,
        description="The notes for the to-do.",
    )
    checklist_items: list[Annotated[str, Field(pattern=r"^[^\r\n]*$")]] | None = Field(
        default=None,
        max_length=100,
        serialization_alias="checklist-items",
        description="Checklist rows. Each item must be a single line.",
    )
    when_date: str | None = Field(
        default=None,
        serialization_alias="when",
        description=(
            "The start date: today, tomorrow, evening, anytime, someday, "
            "or an English date expression. Include a time to set a reminder."
        ),
    )
    deadline_date: str | None = Field(
        default=None,
        serialization_alias="deadline",
        description="The deadline as a date or an English date expression.",
    )
    tags: list[str] | None = Field(
        default=None,
        description="Names of existing tags to apply. Things ignores unknown tags.",
    )
    list: str | None = Field(
        default=None,
        description="The project or area name. Ignored when list_id is supplied.",
    )
    list_id: str | None = Field(
        default=None,
        serialization_alias="list-id",
        description="The project or area ID. Takes precedence over list.",
    )
    heading: str | None = Field(
        default=None,
        description="The heading name within the specified project. It must already exist.",
    )


def build_add_url(payload: AddPayload) -> str:
    """Build a Things add URL without opening it."""
    params = payload.model_dump(by_alias=True, exclude_none=True)
    if "tags" in params:
        params["tags"] = ",".join(params["tags"])
    if "checklist-items" in params:
        params["checklist-items"] = "\n".join(params["checklist-items"])
    return THINGS_ADD_BASE_URL + urlencode(params, quote_via=quote)


async def execute_url(url: str, callbacks: CallbackState) -> CallbackResult:
    """Open an internally built Things URL and wait for its callback."""
    request_id = secrets.token_urlsafe(24)
    future = asyncio.get_running_loop().create_future()
    callbacks.pending[request_id] = future
    callback_urls = {
        f"x-{outcome}": f"{callbacks.base_url}/callbacks/{request_id}/{outcome}"
        for outcome in ("success", "error", "cancel")
    }
    separator = "&" if "?" in url else "?"
    command_url = url + separator + urlencode(callback_urls, quote_via=quote)
    process = None
    try:
        process = await asyncio.create_subprocess_exec(
            "/usr/bin/open",
            command_url,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(process.wait(), timeout=OPEN_TIMEOUT_SECONDS)
        if process.returncode != 0:
            raise ToolError(
                f"macOS could not open the Things URL (exit code {process.returncode})."
            )
        return await asyncio.wait_for(future, timeout=CALLBACK_TIMEOUT_SECONDS)
    except TimeoutError as exc:
        raise ToolError(
            "Timed out waiting for Things. The command outcome is unknown; "
            "do not retry automatically."
        ) from exc
    except OSError as exc:
        raise ToolError("Could not start the macOS Things URL handler.") from exc
    finally:
        callbacks.pending.pop(request_id, None)
        if not future.done():
            future.cancel()
        if process is not None and process.returncode is None:
            with suppress(ProcessLookupError):
                process.kill()
            await process.wait()


@mcp.tool()
async def add_todo(payload: AddPayload, ctx: Context[CallbackState]) -> dict[str, str]:
    """Create one Things to-do and return its ID after Things confirms success.

    Only title is required. A timeout leaves the outcome unknown, so do not retry
    automatically: Things may already have created the to-do.
    """
    result = await execute_url(
        build_add_url(payload), ctx.request_context.lifespan_context
    )
    if result.outcome == "error":
        code = result.parameters.get("errorCode", "unknown")
        message = result.parameters.get(
            "errorMessage", "No error message was supplied."
        )
        raise ToolError(f"Things error {code}: {message}")
    if result.outcome == "cancel":
        raise ToolError("Things canceled the request.")
    todo_id = result.parameters.get("x-things-id", "").strip()
    if not todo_id:
        raise ToolError(
            "Things reported success without a to-do ID. The outcome cannot be "
            "verified; do not retry automatically."
        )
    return {"id": todo_id}
