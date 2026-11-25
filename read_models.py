from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator


class TextFilter(BaseModel):
    """Compare the title or notes with text."""

    field: Literal["title", "notes"]
    operator: Literal["equals", "contains"]
    value: str = Field(description="Text to match exactly or as a substring.")


class DateFilter(BaseModel):
    """Compare a stored date by calendar day, without comparing its time."""

    field: Literal[
        "creation_date",
        "modification_date",
        "deadline_date",
        "activation_date",
        "completion_date",
        "cancellation_date",
    ]
    operator: Literal["eq", "geq", "gt", "lt", "leq"] = Field(
        description=(
            "eq: on; geq: on or after; gt: after; lt: before; leq: on or before."
        )
    )
    value: date = Field(description="Calendar day to compare, in YYYY-MM-DD format.")


class TagFilter(BaseModel):
    """Match one tag name; use multiple filters to request multiple tags."""

    field: Literal["tags"]
    operator: Literal["equals", "contains"]
    value: str = Field(
        description="One tag name to match exactly or as a substring of a tag name."
    )


class StatusFilter(BaseModel):
    """Select items with the specified status."""

    field: Literal["status"]
    operator: Literal["equals"]
    value: Literal["open", "completed", "canceled"]


class CompletionFilter(BaseModel):
    """Select completed or open items; canceled items match neither value."""

    field: Literal["completed"]
    operator: Literal["equals"]
    value: StrictBool = Field(
        description="True selects completed items. False selects only open items."
    )


class ContainerFilter(BaseModel):
    """Compare the name of a containing project or area."""

    field: Literal["project", "area"]
    operator: Literal["equals", "contains"]
    value: str = Field(
        description="Project or area name to match exactly or as a substring."
    )


TodoFilter = Annotated[
    TextFilter
    | DateFilter
    | TagFilter
    | StatusFilter
    | CompletionFilter
    | ContainerFilter,
    Field(discriminator="field"),
]


class FilterGroup(BaseModel):
    """Conditions to combine when selecting Things to-dos."""

    filters: list[TodoFilter] = Field(description="The conditions to evaluate.")
    match: Literal["any", "all"] = Field(
        default="any",
        description="any joins conditions with OR; all joins conditions with AND.",
    )


class SearchScope(BaseModel):
    """Required constraints, independent of the detailed all/any filter group."""

    model_config = ConfigDict(extra="forbid")

    list_name: str | None = Field(
        default=None,
        min_length=1,
        description=(
            "Native Things list name, such as Today, Inbox, or Logbook. "
            "Use its name in the app's language. Preserves native list order."
        ),
    )
    parent_id: str | None = Field(
        default=None,
        min_length=1,
        description="Direct parent project or area ID; excludes child projects.",
    )
    created_on_or_after: date | None = Field(
        default=None,
        description="Earliest creation day, in the Mac's local calendar.",
    )


class SearchRequest(FilterGroup):
    """Search Things to-dos through the bundled read-only AppleScript."""

    model_config = ConfigDict(extra="forbid")

    filters: list[TodoFilter] = Field(
        default_factory=list,
        description="Detailed conditions. An empty list adds no restriction.",
    )
    query: str | None = Field(
        default=None,
        min_length=1,
        description=(
            "Case-insensitive text search across title, notes, tags, project/area "
            "names. Heading and checklist search are not available yet. This "
            "is one condition in the all/any group. Use match=all to require "
            "both the query and the filters."
        ),
    )
    scope: SearchScope = Field(
        default_factory=SearchScope,
        description="Required broad constraints, applied before the detailed group.",
    )


class TodoRecord(BaseModel):
    """A public AppleScript record; unsupported fields are unknown, not empty."""

    id: str = Field(min_length=1)
    title: str
    notes: str
    tags: list[str]
    status: Literal["open", "completed", "canceled"]
    activation_date: date | None
    deadline_date: date | None
    creation_date: datetime
    modification_date: datetime
    project: str | None
    area: str | None
    list_id: str | None
    when_date: str | None = Field(
        description=(
            "Known activation day only. Null does not distinguish Anytime "
            "from Someday; reminder and evening details are unavailable."
        ),
    )
    completion_date: datetime | None
    cancellation_date: datetime | None
    list: str | None
    checklist_items: None = Field(
        default=None, description="Unavailable through AppleScript."
    )
    heading: None = Field(default=None, description="Unavailable through AppleScript.")
    reminder_date: None = Field(
        default=None, description="Unavailable through AppleScript."
    )
    evening: None = Field(default=None, description="Unavailable through AppleScript.")
    start: None = Field(default=None, description="Anytime/Someday state is not read yet.")
    is_inbox: None = Field(default=None, description="Not read in the core record.")
    is_logged: None = Field(default=None, description="Not read in the core record.")

    @model_validator(mode="before")
    @classmethod
    def derive_display_fields(cls, value):
        if not isinstance(value, dict):
            return value
        value = value.copy()
        if "when_date" not in value:
            activation = value.get("activation_date")
            value["when_date"] = (
                activation.isoformat() if isinstance(activation, date) else activation
            )
        if "list" not in value:
            value["list"] = value.get("project") or value.get("area") or None
        return value


class ReadBatch(BaseModel):
    """Records from the native collection before detailed Python filtering."""

    items: list[TodoRecord]
    candidate_count: int = Field(ge=0)

    @model_validator(mode="after")
    def check_count(self):
        if len(self.items) != self.candidate_count:
            raise ValueError("Export every candidate before applying Python filters.")
        return self


class SearchResult(BaseModel):
    items: list[TodoRecord]
    candidate_count: int = Field(
        ge=0,
        description="Candidate count before Python filtering and deduplication.",
    )
    possibly_truncated: Literal[False] = Field(
        default=False, description="AppleScript reads have no artificial result cap.",
    )
    unavailable_fields: list[str] = Field(
        default_factory=lambda: [
            "checklist_items", "heading", "reminder_date", "evening",
            "start", "is_inbox", "is_logged",
        ],
        description="Fields not read by this backend; their null values mean unknown.",
    )
