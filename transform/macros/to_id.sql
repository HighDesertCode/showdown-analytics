{#- Converts a display name to a Showdown ID, like Showdown's toID: "Iron Valiant" -> "ironvaliant". -#}
{% macro to_id(column) -%}
    REGEXP_REPLACE(LOWER({{ column }}), '[^a-z0-9]', '', 'g')
{%- endmacro %}
