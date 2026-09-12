import argparse
from pathlib import Path

import pandas as pd

from app.db.supabase import get_supabase_client


def clean(value):
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


def records_with_metadata(df: pd.DataFrame, source_file: str) -> list[dict]:
    output = []
    for index, row in df.iterrows():
        raw = {column: clean(value) for column, value in row.to_dict().items()}
        output.append(
            {
                "source_file": source_file,
                "source_row_number": int(index) + 2,  # header is row 1
                "raw_payload": raw,
                **raw,
            }
        )
    return output


def batches(items: list[dict], size: int = 100):
    for start in range(0, len(items), size):
        yield items[start : start + size]


def import_reports(db, path: Path):
    df = pd.read_csv(path)
    rows = []
    for item in records_with_metadata(df, path.name):
        raw = item["raw_payload"]
        rows.append(
            {
                "source_file": item["source_file"],
                "source_row_number": item["source_row_number"],
                "source_report_id": raw.get("report_id"),
                "channel": raw.get("channel"),
                "received_at": raw.get("received_at"),
                "reporter_name": raw.get("reporter_name"),
                "reporter_contact": raw.get("reporter_contact"),
                "location_text": raw.get("location_text"),
                "latitude": raw.get("latitude"),
                "longitude": raw.get("longitude"),
                "description": raw.get("description"),
                "category": raw.get("category"),
                "urgency": raw.get("urgency"),
                "photo": raw.get("photo"),
                "source_status": raw.get("status"),
                "raw_payload": raw,
            }
        )

    for batch in batches(rows):
        db.table("raw_reports").upsert(
            batch,
            on_conflict="source_file,source_row_number",
        ).execute()

    print(f"Imported {len(rows)} report rows.")


def import_assets(db, path: Path):
    df = pd.read_csv(path)
    rows = []
    for item in records_with_metadata(df, path.name):
        raw = item["raw_payload"]
        rows.append(
            {
                "source_file": item["source_file"],
                "source_row_number": item["source_row_number"],
                "road_name": raw.get("road_name"),
                "also_known_as": raw.get("also_known_as"),
                "road_class": raw.get("road_class"),
                "ward": raw.get("ward"),
                "asset_type": raw.get("asset_type"),
                "asset_id": raw.get("asset_id"),
                "nearest_facility": raw.get("nearest_facility"),
                "facility_distance_m": raw.get("facility_distance_m"),
                "raw_payload": raw,
            }
        )

    for batch in batches(rows):
        db.table("assets").upsert(
            batch,
            on_conflict="source_file,source_row_number",
        ).execute()

    print(f"Imported {len(rows)} asset rows.")


def import_jobs(db, path: Path):
    df = pd.read_csv(path)
    rows = []
    for item in records_with_metadata(df, path.name):
        raw = item["raw_payload"]
        rows.append(
            {
                "source_file": item["source_file"],
                "source_row_number": item["source_row_number"],
                "source_job_id": raw.get("job_id"),
                "completed_date": raw.get("completed_date"),
                "crew": raw.get("crew"),
                "work_type": raw.get("work_type"),
                "road_name": raw.get("road_name"),
                "notes": raw.get("notes"),
                "raw_payload": raw,
            }
        )

    for batch in batches(rows):
        db.table("jobs_history").upsert(
            batch,
            on_conflict="source_file,source_row_number",
        ).execute()

    print(f"Imported {len(rows)} job-history rows.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("../data/source"),
        help="Directory containing reports.csv, assets.csv, jobs-history.csv",
    )
    args = parser.parse_args()

    data_dir = args.data_dir.resolve()
    required = {
        "reports": data_dir / "reports.csv",
        "assets": data_dir / "assets.csv",
        "jobs": data_dir / "jobs-history.csv",
    }

    missing = [str(path) for path in required.values() if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing source file(s): {missing}")

    db = get_supabase_client()
    import_reports(db, required["reports"])
    import_assets(db, required["assets"])
    import_jobs(db, required["jobs"])

    print("Source data import complete.")


if __name__ == "__main__":
    main()
