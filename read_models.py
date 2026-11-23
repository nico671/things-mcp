from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StrictBool


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
