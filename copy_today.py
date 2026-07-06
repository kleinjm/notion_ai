"""Copy source-DB rows with Today=true into the target DB, stamp them with
today's date, then flip Today back to false on the source rows.

Runs locally (reads .env) and in GitHub Actions (reads real env vars).
"""

import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from notion_client import Client

load_dotenv()

TOKEN = os.environ.get("NOTION_PAT") or os.environ.get("NOTION_TOKEN")
SOURCE_DB_ID = os.environ.get("SOURCE_DB_ID")
TARGET_DB_ID = os.environ.get("TARGET_DB_ID")
TODAY_PROP = os.environ.get("TODAY_PROP", "Today")
TARGET_DATE_PROP = os.environ.get("TARGET_DATE_PROP", "").strip()
TEST_PAGE_ID = os.environ.get("TEST_PAGE_ID", "").strip()
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"

# Property types we can write back verbatim. Read-only/computed types
# (formula, rollup, created_time, etc.) are skipped automatically.
COPYABLE_TYPES = {
    "title", "rich_text", "number", "select", "multi_select", "status",
    "date", "checkbox", "url", "email", "phone_number", "people",
    "relation", "files",
}


def require(name, value):
    if not value:
        sys.exit(f"Missing required config: {name}")


def extract_value(prop):
    """Pull the writable payload out of a property value object."""
    t = prop["type"]
    if t not in COPYABLE_TYPES:
        return None
    v = prop.get(t)
    if v is None or v == [] or v == "":
        return None
    if t in ("select", "status"):
        return {"name": v["name"]}
    if t == "multi_select":
        return [{"name": o["name"]} for o in v]
    if t == "people":
        return [{"id": p["id"]} for p in v]
    if t == "relation":
        return [{"id": r["id"]} for r in v]
    if t == "files":
        # Only external files can be re-written; uploaded files can't.
        out = [f for f in v if f.get("type") == "external"]
        return out or None
    return v  # title, rich_text, number, date, checkbox, url, email, phone_number


def find_prop_by_type(schema_props, wanted_type):
    for name, meta in schema_props.items():
        if meta["type"] == wanted_type:
            return name
    return None


def main():
    require("NOTION_TOKEN", TOKEN)
    require("SOURCE_DB_ID", SOURCE_DB_ID)
    require("TARGET_DB_ID", TARGET_DB_ID)

    notion = Client(auth=TOKEN)

    source_db = notion.databases.retrieve(SOURCE_DB_ID)
    target_db = notion.databases.retrieve(TARGET_DB_ID)
    source_props = source_db["properties"]
    target_props = target_db["properties"]

    if TODAY_PROP not in source_props:
        sys.exit(f"Source DB has no property named {TODAY_PROP!r}. "
                 f"Available: {list(source_props)}")

    # Which target date property to stamp with today's date.
    date_prop = TARGET_DATE_PROP or find_prop_by_type(target_props, "date")
    if not date_prop:
        sys.exit("No date property found on target DB; set TARGET_DATE_PROP.")
    if date_prop not in target_props or target_props[date_prop]["type"] != "date":
        sys.exit(f"Target date property {date_prop!r} is missing or not a date.")

    # Optional: a relation on the target that points back to the source DB,
    # so each log row links to its exercise. Auto-detect unless overridden.
    relation_prop = os.environ.get("TARGET_RELATION_PROP", "").strip()
    if not relation_prop:
        for name, meta in target_props.items():
            if meta["type"] == "relation" and \
                    meta["relation"].get("database_id", "").replace("-", "") == \
                    SOURCE_DB_ID.replace("-", ""):
                relation_prop = name
                break

    # Stamp with the date in the configured timezone (default Pacific), not the
    # runner's UTC clock — GitHub Actions runners are always UTC.
    tz = ZoneInfo(os.environ.get("TIMEZONE", "America/Los_Angeles"))
    today_iso = datetime.now(tz).date().isoformat()
    print(f"Mode: {'DRY RUN' if DRY_RUN else 'LIVE'} | date stamp: {today_iso}")
    print(f"Target date property: {date_prop!r}")
    print(f"Target relation to source: {relation_prop or '(none)'}")

    # Gather rows to process.
    if TEST_PAGE_ID:
        page = notion.pages.retrieve(TEST_PAGE_ID)
        rows = [page]
        print(f"TEST MODE: single page {TEST_PAGE_ID}")
    else:
        rows = []
        cursor = None
        while True:
            resp = notion.databases.query(
                database_id=SOURCE_DB_ID,
                filter={"property": TODAY_PROP, "checkbox": {"equals": True}},
                start_cursor=cursor,
            )
            rows.extend(resp["results"])
            if not resp.get("has_more"):
                break
            cursor = resp["next_cursor"]

    print(f"Found {len(rows)} row(s) to process.\n")

    for row in rows:
        # Build target properties from matching names+types.
        new_props = {}
        for name, prop in row["properties"].items():
            if name not in target_props:
                continue
            if target_props[name]["type"] != prop["type"]:
                continue
            val = extract_value(prop)
            if val is not None:
                new_props[name] = {prop["type"]: val}

        # Stamp the date.
        new_props[date_prop] = {"date": {"start": today_iso}}

        # Link the log row back to its source exercise.
        if relation_prop:
            new_props[relation_prop] = {"relation": [{"id": row["id"]}]}

        title = _title_of(row)
        print(f"- {title}")
        print(f"    -> copy {len(new_props)} propert(y/ies) to target, "
              f"stamp {date_prop}={today_iso}, then set {TODAY_PROP}=false")

        if DRY_RUN:
            continue

        notion.pages.create(
            parent={"database_id": TARGET_DB_ID},
            properties=new_props,
        )
        notion.pages.update(
            page_id=row["id"],
            properties={TODAY_PROP: {"checkbox": False}},
        )
        print("    done.")

    print("\nComplete.")


def _title_of(page):
    for prop in page["properties"].values():
        if prop["type"] == "title":
            parts = prop["title"]
            return "".join(p["plain_text"] for p in parts) or "(untitled)"
    return "(no title prop)"


if __name__ == "__main__":
    main()
