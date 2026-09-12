"""CSV ingestion for the AI pipeline (Person A, Step 1).

Loads reports.csv, assets.csv and jobs-history.csv into their raw Supabase
tables. Deterministic only — no AI calls here.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

BATCH_SIZE = 100

REPORTS_FILE = "reports.csv"
ASSETS_FILE = "assets.csv"
JOBS_HISTORY_FILE = "jobs-history.csv"

# received_at formats seen in reports.csv beyond plain ISO 8601.
_EXTRA_DATE_FORMATS = ["%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S"]


def _clean_value(value):
    """Convert pandas NaN / numpy scalars to plain Python values."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


def _clean_text(value) -> str | None:
    value = _clean_value(value)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_float(value) -> float | None:
    value = _clean_value(value)
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_received_at(value) -> tuple[str | None, bool]:
    """Normalize received_at to ISO 8601. Returns (value, parsed_ok)."""
    text = _clean_text(value)
    if text is None:
        return None, True

    try:
        return datetime.fromisoformat(text).isoformat(), True
    except ValueError:
        pass

    for fmt in _EXTRA_DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).isoformat(), True
        except ValueError:
            continue

    logger.warning("Could not parse received_at value: %r", text)
    return text, False


def _read_rows(csv_path: Path) -> list[dict]:
    df = pd.read_csv(csv_path, dtype=str)
    return [
        {column: _clean_value(value) for column, value in row.to_dict().items()}
        for _, row in df.iterrows()
    ]


def _upsert_batches(supabase, table: str, rows: list[dict], on_conflict: str) -> dict:
    stats = {"loaded": 0, "skipped": 0, "errors": 0}
    for start in range(0, len(rows), BATCH_SIZE):
        batch = rows[start : start + BATCH_SIZE]
        try:
            supabase.table(table).upsert(batch, on_conflict=on_conflict).execute()
            stats["loaded"] += len(batch)
        except Exception:
            logger.exception(
                "Failed to upsert rows %s-%s into %s", start, start + len(batch), table
            )
            stats["errors"] += len(batch)
    return stats


def load_reports(supabase, csv_path: str) -> dict:
    """Load reports.csv into raw_reports. Returns {"loaded", "skipped", "errors"}."""
    path = Path(csv_path)
    rows = []
    for index, raw in enumerate(_read_rows(path)):
        received_at, parsed_ok = _parse_received_at(raw.get("received_at"))
        rows.append(
            {
                "source_file": REPORTS_FILE,
                "source_row_number": index + 1,
                "source_report_id": _clean_text(raw.get("report_id")),
                "channel": _clean_text(raw.get("channel")),
                "received_at": received_at,
                "reporter_name": _clean_text(raw.get("reporter_name")),
                "reporter_contact": _clean_text(raw.get("reporter_contact")),
                "location_text": _clean_text(raw.get("location_text")),
                "latitude": _parse_float(raw.get("latitude")),
                "longitude": _parse_float(raw.get("longitude")),
                "description": _clean_text(raw.get("description")),
                "category": _clean_text(raw.get("category")),
                "urgency": _clean_text(raw.get("urgency")),
                "photo": _clean_text(raw.get("photo")),
                "source_status": _clean_text(raw.get("status")),
                "needs_review": not parsed_ok,
                "raw_payload": raw,
            }
        )

    stats = _upsert_batches(supabase, "raw_reports", rows, "source_file,source_row_number")
    logger.info("raw_reports: loaded=%s errors=%s", stats["loaded"], stats["errors"])
    return stats


def load_assets(supabase, csv_path: str) -> dict:
    """Load assets.csv into assets. Returns {"loaded", "skipped", "errors"}."""
    path = Path(csv_path)
    rows = []
    for index, raw in enumerate(_read_rows(path)):
        rows.append(
            {
                "source_file": ASSETS_FILE,
                "source_row_number": index + 1,
                "road_name": _clean_text(raw.get("road_name")),
                "also_known_as": _clean_text(raw.get("also_known_as")),
                "road_class": _clean_text(raw.get("road_class")),
                "ward": _clean_text(raw.get("ward")),
                "asset_type": _clean_text(raw.get("asset_type")),
                "asset_id": _clean_text(raw.get("asset_id")),
                "nearest_facility": _clean_text(raw.get("nearest_facility")),
                "facility_distance_m": _parse_float(raw.get("facility_distance_m")),
                "raw_payload": raw,
            }
        )

    stats = _upsert_batches(supabase, "assets", rows, "source_file,source_row_number")
    logger.info("assets: loaded=%s errors=%s", stats["loaded"], stats["errors"])
    return stats


def load_jobs_history(supabase, csv_path: str) -> dict:
    """Load jobs-history.csv into jobs_history. Returns {"loaded", "skipped", "errors"}."""
    path = Path(csv_path)
    rows = []
    for index, raw in enumerate(_read_rows(path)):
        rows.append(
            {
                "source_file": JOBS_HISTORY_FILE,
                "source_row_number": index + 1,
                "source_job_id": _clean_text(raw.get("job_id")),
                "completed_date": _clean_text(raw.get("completed_date")),
                "crew": _clean_text(raw.get("crew")),
                "work_type": _clean_text(raw.get("work_type")),
                "road_name": _clean_text(raw.get("road_name")),
                "notes": _clean_text(raw.get("notes")),
                "raw_payload": raw,
            }
        )

    stats = _upsert_batches(supabase, "jobs_history", rows, "source_file,source_row_number")
    logger.info("jobs_history: loaded=%s errors=%s", stats["loaded"], stats["errors"])
    return stats


def load_all(supabase, data_dir: str) -> dict:
    """Load all 3 source files. Returns combined stats per table."""
    base = Path(data_dir)
    return {
        "raw_reports": load_reports(supabase, str(base / REPORTS_FILE)),
        "assets": load_assets(supabase, str(base / ASSETS_FILE)),
        "jobs_history": load_jobs_history(supabase, str(base / JOBS_HISTORY_FILE)),
    }
