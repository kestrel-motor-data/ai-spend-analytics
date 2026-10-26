select
  -- Version 2 (usage from 2027-04-09) reports the day in UTC as
  -- usage_date_utc instead of usage_date in US Central. Each day is one
  -- version only, so exactly one of the two is populated per row.
  coalesce(usage_date, usage_date_utc) as usage_date,
  -- Version 2 renames api_key_id to key_id; same values.
  coalesce(api_key_id, key_id) as api_key_id,
  -- Version 2 splits deployment into deployment_name and model. We keep
  -- reporting the deployment name here, as before, so the report's "model"
  -- column for Azure doesn't change shape mid-migration.
  coalesce(deployment, deployment_name) as deployment,
  -- Version 2 splits input_tokens into prompt_tokens (excl. cache) and
  -- cached_prompt_tokens; add them back together for a like-for-like count.
  coalesce(input_tokens, prompt_tokens + cached_prompt_tokens) as input_tokens,
  -- Version 2 renames output_tokens to completion_tokens; same values.
  coalesce(output_tokens, completion_tokens) as output_tokens,
  -- Azure renamed the billed-cost column from cost_usd to cost in the
  -- 2027-03-23 export, then to billed_amount in version 2 (2027-04-09).
  -- Coalesce so all three periods resolve to one not-null cost figure.
  cast(coalesce(cost_usd, cost, billed_amount) as numeric) as cost_usd,
  _load_id,
  _loaded_at
from {{ source('raw', 'azure_openai_usage') }}
