select
  usage_date,
  api_key_id,
  deployment,
  input_tokens,
  output_tokens,
  cast(cost_usd as numeric) as cost_usd,
  _load_id,
  _loaded_at
from {{ source('raw', 'azure_openai_usage') }}
