{#- Put models in the schema their folder sets (staging or api) exactly, instead of dbt's default
    "<profile schema>_<folder schema>" (e.g. "staging_api"). -#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ custom_schema_name if custom_schema_name is not none else target.schema }}
{%- endmacro %}
