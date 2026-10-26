select
  department_id,
  name as department,
  plant,
  cost_centre
from {{ source('raw', 'departments') }}
