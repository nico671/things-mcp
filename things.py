from typing import Annotated
from urllib.parse import quote, urlencode

from mcp.server import MCPServer
from pydantic import BaseModel, Field

mcp = MCPServer("things-mcp")

THINGS_ADD_BASE_URL = "things:///add?"


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
