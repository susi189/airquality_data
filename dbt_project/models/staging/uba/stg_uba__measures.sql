with source as (
    select * from {{ source('uba', 'measures') }}
),

renamed as (
    select
        cast(station_id as integer)                 as station_id,
        component_id,
        scope_id,
        -- The API gives the start of the hour in local time (CET/CEST)
        cast(date_start as timestamp)               as measured_from_local,
        value,
        -- `index` is a pollutant-specific band derived from `value`, not an air quality index
        try_cast("index" as integer)                as value_class
    from source
)

select
    concat_ws('-', station_id, component_id, scope_id, strftime(measured_from_local, '%Y%m%d%H')) as measure_key,
    station_id,
    component_id,
    scope_id,
    measured_from_local,
    -- `date_end` is not parsed: the last hour of a day ends at '24:00:00', which is not a valid timestamp
    measured_from_local + interval 1 hour                                    as measured_to_local,
    timezone('UTC', timezone('Europe/Berlin', measured_from_local))          as measured_from_utc,
    value,
    value_class
from renamed
