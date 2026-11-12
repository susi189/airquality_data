{#
    Use custom schema names as-is (`staging`, `marts`) instead of dbts default
    `<target schema>_<custom schema>` (e.g. `main_staging`). Models without a
    custom schema fall back to the target schema from profiles.yml.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
