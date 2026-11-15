-- Each usage_date in the raw table should come from exactly one load.
-- replace_day deletes a day before re-appending it, so more than one
-- _load_id for the same day means a row was inserted outside the normal
-- ingest path (e.g. a manual backfill query), and staging's dedupe would
-- silently mask it by keeping only the most-recently-loaded rows. This
-- test checks raw directly so a repeat of DATA14D-122 is caught even
-- though staging no longer shows duplicates.
--
-- 2027-03-17 is excluded: it was double-loaded by a manual query on
-- 2027-04-01 (DATA14D-122), raw rows are never deleted by hand per the
-- runbook, and staging's dedupe already corrects the reported figures.
-- This is the one known, permanent exception; any other date failing
-- this test is a new incident.
select
  coalesce(usage_date, usage_date_utc) as usage_date,
  count(distinct _load_id) as load_id_count
from {{ source('raw', 'azure_openai_usage') }}
where coalesce(usage_date, usage_date_utc) != '2027-03-17'
group by 1
having count(distinct _load_id) > 1
