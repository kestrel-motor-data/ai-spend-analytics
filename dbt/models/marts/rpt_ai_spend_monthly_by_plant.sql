-- Finance's site reviews want the monthly report by plant and cost centre.
select
  r.month,
  r.department,
  d.plant,
  d.cost_centre,
  r.tool,
  r.cost,
  r.budget,
  r.variance
from {{ ref('rpt_ai_spend_monthly') }} r
left join {{ ref('stg_departments') }} d on d.department = r.department
