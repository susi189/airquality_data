with source as (
    select * from {{ source('uba', 'components') }}
),

renamed as (
    select
        cast(component_id as integer)                                       as component_id,
        component_code,
        case when component_code = 'PM2' then 'PM2.5' else component_code end as pollutant,
        component_symbol,
        component_name,
        component_unit                                                      as unit
    from source
)

select * from renamed