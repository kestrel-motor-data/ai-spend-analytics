-- One row per day the seat snapshot was taken, per currently assigned seat.
-- The vendor API has no removal date or history endpoint: a seat simply
-- stops appearing once revoked. created_at lets a backfill exclude days
-- before the seat existed, but it cannot recover days a now-revoked seat
-- was still held, since that day's load only sees who holds it today.
select
  cast(day as date) as day,
  login as github_login,
  plan_type,
  cast(created_at as date) as created_at,
  cast(monthly_cost_usd as numeric) as monthly_cost_usd
from {{ source('raw', 'github_copilot_seats') }}
