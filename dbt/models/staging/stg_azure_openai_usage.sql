-- Azure OpenAI's usage export moved to a v2 format starting with usage for
-- 2027-04-09 (DATA14D-114): usage_date -> usage_date_utc (UTC, not US
-- Central -- daily totals shift by a few hours' worth of usage right at the
-- cutover, a one-time, expected discontinuity, not a data error),
-- api_key_id -> key_id, deployment -> deployment_name (+ a new `model`
-- field for the true base model, not used here -- we still report the
-- deployment name as `deployment`, same as before v2), input_tokens ->
-- prompt_tokens + cached_prompt_tokens, output_tokens -> completion_tokens,
-- cost_usd -> billed_amount. v1 rows only have the old columns, v2 rows
-- only have the new ones, so every renamed field is coalesced the same way
-- the 2027-03-23 cost_usd -> cost rename was handled.
--
-- DATA14D-122: on 2027-04-01 a manual backfill query re-inserted
-- 2027-03-17's rows under a new _load_id, double-counting the day by
-- $3,029.03 in March's report. Per the runbook, raw rows are never deleted
-- and duplicates are removed here instead: keep only the most recently
-- loaded row per usage_date/api_key_id/deployment.
select
  usage_date,
  api_key_id,
  deployment,
  input_tokens,
  output_tokens,
  cost_usd,
  _load_id,
  _loaded_at
from (
  select
    coalesce(usage_date, usage_date_utc) as usage_date,
    coalesce(api_key_id, key_id) as api_key_id,
    coalesce(deployment, deployment_name) as deployment,
    coalesce(input_tokens, prompt_tokens + cached_prompt_tokens) as input_tokens,
    coalesce(output_tokens, completion_tokens) as output_tokens,
    cast(coalesce(cost_usd, cost, billed_amount) as numeric) as cost_usd,
    _load_id,
    _loaded_at
  from {{ source('raw', 'azure_openai_usage') }}
)
qualify row_number() over (
  partition by usage_date, api_key_id, deployment
  order by _loaded_at desc
) = 1
