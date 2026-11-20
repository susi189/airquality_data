{{ config(severity='warn') }}

-- Stations should not report values after their closing date. The API data has known exceptions,
-- so this warns instead of failing the build.
select
    m.station_id,
    s.station_code,
    s.active_to,
    max(m.measured_from_local) as last_measured_at
from {{ ref('stg_uba__measures') }} as m
inner join {{ ref('stg_uba__stations') }} as s using (station_id)
where s.active_to is not null
  and m.value is not null
  and cast(m.measured_from_local as date) > s.active_to
group by 1, 2, 3
