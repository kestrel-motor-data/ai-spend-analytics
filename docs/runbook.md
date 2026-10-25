# AI spend pipeline runbook

How the pipeline behind the executive **AI Spend** report works, how to fix it,
and who to tell. Times are US Central.

## What runs

| When | What |
|---|---|
| 01:30 | Vendors' daily files land in the landing bucket (`gs://<LANDING_BUCKET>/<source>/usage_YYYY-MM-DD.csv`) |
| 02:00 | `nightly.yml` loads yesterday's files into `raw`, then `dbt build` rebuilds `staging` and `marts` |
| Every pull request | `ci.yml` builds the changed models into the `ci` dataset against real `raw` data |

The report reads `marts.fct_ai_spend_daily` and `marts.rpt_ai_spend_monthly`.

## Datasets

| Dataset | Written by | Notes |
|---|---|---|
| `raw` | `nightly.yml` only | One table per source. Every row has `_load_id` and `_loaded_at`. Never edit by hand. |
| `staging` | `nightly.yml` only | One cleaned model per raw table (`stg_*`) |
| `marts` | `nightly.yml` only | `fct_ai_spend_daily`, `rpt_ai_spend_monthly`, `dim_department` |
| `finance` | Finance | `vendor_invoices` (vendor, month, amount): the source of truth for what we paid |
| `scratch_employee` | The data engineer | Your own area for trying things. Nothing reads from it. |
| `ci` | `ci.yml` | Overwritten by every pull request build |

Every query is capped at **1 GB scanned**. Filter on dates.

## How a load works

`ingest/<source>.py` reads one day's landed file and calls `replace_day`,
which deletes that day from the raw table and appends the file under a new
`_load_id`. Re-running a day replaces it, so a reload never duplicates rows.
Columns a vendor adds are added to the raw table, not dropped.

Models are rebuilt in full on every run, so reloading one day changes only that day.

## Reload days

Only reviewed code on `main` can load. Start a run from the Actions tab, or:

```
gh workflow run nightly.yml -f start_date=2027-03-21 -f end_date=2027-03-21
gh workflow run nightly.yml -f skip_ingest=true      # rebuild models only
```

Then check the totals for the reloaded days in `marts.fct_ai_spend_daily`.

## Adding a source

1. Read the vendor's API docs. Follow pagination until there is no next page,
   and back off when rate limited.
2. Add `ingest/<source>.py` with a `load(day)` that writes through
   `replace_day`, and register it in `ingest/run.py`. The first load creates the
   raw table `raw.<source>_usage`; rows must carry the usage date as `YYYY-MM-DD`.
3. Add `stg_<source>` with a description for every column and tests.
4. Add the source to `fct_ai_spend_daily` and to the `tool` accepted values.
5. Try the SQL in `scratch_employee` first, open **one** pull request, and wait
   for `ci.yml` to pass.
6. After the merge, load the history with `nightly.yml` and check the report tables.

**Unmatched people.** Usage that can't be matched to someone in
`raw.hr_employees` (a GitHub login, a key or a user with no HR record) is kept
under department `Unallocated`, never dropped. Say how many in the pull request.

**Seat licences** cost their monthly price spread evenly over the days of the
month, like Microsoft 365 Copilot.

## Credentials

Vendor API tokens live in the `production` environment's secrets as
`<SOURCE>_API_TOKEN`, for example `COPILOT_API_TOKEN`, and reach code as
environment variables. A token you're given to explore an API is for your own
calls only. Never put a token in code, a commit, a pull request, a ticket or a chat.

## Rules

- Every change to code or data goes through a pull request with one human
  approval and a green `ci.yml`. Nobody pushes to `main`.
- Never write to `raw`, `staging` or `marts` directly, and never change a report
  number by hand. Fix the cause in code, then reload.
- Never delete raw rows. Duplicates are removed in the cleaned models.
- `hr_employees.email` and `hr_employees.name` are personal data. Never put them
  in chat, email or tickets; share counts by department instead.

## When something breaks

1. Reply in **Data Alerts** that you're looking, within 15 minutes.
2. Read the failed run's log and the landed file, and name the cause.
3. Fix it in a pull request, with a test that would have caught it.
4. Open a `DATA14D` ticket with cause, impact (which days, which tool, which
   report tables) and the fix.
5. Tell your manager. If report figures are behind or wrong, say so in
   **AI Spend Report**.
6. After the merge, reload only the affected days and check the totals.
7. Say in **AI Spend Report** that the figures are current, and close the ticket.

## Who to tell

| Who | Where | When |
|---|---|---|
| Data platform lead (your manager) | Direct message | Anything broken, any decision |
| Report readers and Finance | AI Spend Report channel | Figures late, wrong, or corrected |
| Pipeline failures | Data Alerts channel | Every failed run |
