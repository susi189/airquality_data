with source as (
    select * from {{ source('uba', 'stations') }}
),

renamed as (
    select
        cast(station_id as integer)                     as station_id,
        station_code,
        station_name,
        nullif(station_synonym, '')                     as station_synonym,
        nullif(station_city, '')                        as city,
        nullif(station_street, '')                      as street,
        nullif(station_street_nr, '')                   as street_nr,
        nullif(station_zip_code, '')                    as zip_code,
        cast(nullif(station_latitude, '') as double)    as latitude,
        cast(nullif(station_longitude, '') as double)   as longitude,
        cast(nullif(station_active_from, '') as date)   as active_from,
        -- Empty means the station is still operating
        cast(nullif(station_active_to, '') as date)     as active_to,
        network_code,
        network_name,
        station_type_name                               as station_type,
        station_setting_short_name                      as area_type
    from source
)

select
    *,
    -- Evaluated at query time (staging is a view), so it is always relative to today
    active_to is null or active_to >= current_date as is_active
from renamed
