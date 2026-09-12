"""Raw resident report as served by the API."""

from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class ReportOut(BaseModel):
    """One row of raw_reports.

    `id` is the database key. `source_report_id` is the ID from reports.csv and
    is NOT unique -- the supplied data repeats report IDs (CLAUDE.md section 10),
    so never key anything off it.
    """

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str | None = None
    source_report_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("source_report_id", "report_id"),
    )
    channel: str | None = None
    received_at: datetime | None = None
    reporter_name: str | None = None
    location_text: str | None = Field(
        default=None,
        validation_alias=AliasChoices("location_text", "location_raw"),
    )
    normalized_location: str | None = None
    description: str | None = None
    category: str | None = None
    urgency: str | None = None
    needs_review: bool = False

    # Traceability back to the immutable CSV (CLAUDE.md section 10).
    source_file: str | None = None
    source_row_number: int | None = None
