select
  usage_date,
  api_key_id,
  deployment,
  input_tokens,
  output_tokens,
  -- Azure renamed the billed-cost column from cost_usd to cost in the
  -- 2027-03-23 export. Old rows still have cost_usd; new rows only have
  -- cost. Coalesce so both periods resolve to one not-null cost figure.
  cast(coalesce(cost_usd, cost) as numeric) as cost_usd,
  _load_id,
  _loaded_at
from {{ source('raw', 'azure_openai_usage') }}
