select
  day,
  login as github_login,
  editor,
  suggestions_count,
  acceptances_count,
  lines_accepted,
  chat_turns
from {{ source('raw', 'github_copilot_usage') }}
