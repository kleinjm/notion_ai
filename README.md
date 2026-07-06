# notion_ai

Personal automation for my Notion workspace.

## `copy_today.py`

Copies every row in the **source** database whose `Today` checkbox is `true`
into the **target** database, stamps each copy with today's date, then flips
the source rows' `Today` checkbox back to `false`. Runs daily via GitHub Actions.

### Setup

1. **Create a Notion integration**
   - Go to https://www.notion.so/my-integrations → *New integration* (internal).
   - Copy the *Internal Integration Secret* (starts with `ntn_`).
2. **Share both databases with the integration**
   - Open each database → `•••` menu → *Connections* → add your integration.
   - Do this for BOTH the source and target databases.
3. **Local config**
   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env   # then fill in NOTION_TOKEN
   ```

### Test (single record, safe)

```bash
# Dry run — reads only, writes nothing:
DRY_RUN=true python copy_today.py

# Live test on the one Crab Walks record (TEST_PAGE_ID is set in .env):
python copy_today.py
```

Remove/blank `TEST_PAGE_ID` in `.env` to process all matching rows.

### GitHub Actions

- Repo **Secret**: `NOTION_TOKEN`
- Repo **Variables**: `SOURCE_DB_ID`, `TARGET_DB_ID`, `TODAY_PROP`,
  `TARGET_DATE_PROP` (leave date prop blank to auto-detect).
- Schedule is in `.github/workflows/daily.yml` (UTC). Trigger manually from the
  Actions tab via *Run workflow*.
