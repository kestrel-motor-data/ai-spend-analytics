select
  workspace_id,
  name as workspace_name,
  department
from {{ source('raw', 'anthropic_workspaces') }}
