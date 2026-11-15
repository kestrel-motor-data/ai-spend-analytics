-- Kestrel's Anthropic usage proxy has no cost endpoint, so cost is computed
-- here from token counts against Kestrel's published price table (USD per
-- million tokens). The proxy's docs say "all cache writes are 5-minute
-- writes", so cache_creation_1h_input_tokens is always 0 today; it is kept
-- in the sum and billed at the 5-minute write rate so this still holds if
-- Anthropic ever starts returning 1-hour cache writes.
with priced as (
  select
    day,
    workspace_id,
    model,
    uncached_input_tokens,
    cache_read_input_tokens,
    cache_creation_5m_input_tokens,
    cache_creation_1h_input_tokens,
    output_tokens,
    case model
      when 'claude-sonnet-4-5' then 3.00
      when 'claude-haiku-4-5' then 1.00
      when 'claude-opus-4-1' then 15.00
    end as input_price_per_mtok,
    case model
      when 'claude-sonnet-4-5' then 15.00
      when 'claude-haiku-4-5' then 5.00
      when 'claude-opus-4-1' then 75.00
    end as output_price_per_mtok,
    case model
      when 'claude-sonnet-4-5' then 3.75
      when 'claude-haiku-4-5' then 1.25
      when 'claude-opus-4-1' then 18.75
    end as cache_write_price_per_mtok,
    case model
      when 'claude-sonnet-4-5' then 0.30
      when 'claude-haiku-4-5' then 0.10
      when 'claude-opus-4-1' then 1.50
    end as cache_read_price_per_mtok,
    _load_id,
    _loaded_at
  from {{ source('raw', 'anthropic_usage') }}
)

select
  day,
  workspace_id,
  model,
  uncached_input_tokens,
  cache_read_input_tokens,
  cache_creation_5m_input_tokens,
  cache_creation_1h_input_tokens,
  output_tokens,
  uncached_input_tokens + cache_read_input_tokens
    + cache_creation_5m_input_tokens + cache_creation_1h_input_tokens
    + output_tokens as total_tokens,
  (uncached_input_tokens * input_price_per_mtok
    + output_tokens * output_price_per_mtok
    + (cache_creation_5m_input_tokens + cache_creation_1h_input_tokens) * cache_write_price_per_mtok
    + cache_read_input_tokens * cache_read_price_per_mtok) / 1000000 as cost_usd,
  _load_id,
  _loaded_at
from priced
