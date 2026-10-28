{#- Converts a display name to a Showdown ID, like Showdown's toID: "Iron Valiant" -> "ironvaliant". -#}
{% macro to_id(column) -%}
    regexp_replace(lower({{ column }}), '[^a-z0-9]', '', 'g')
{%- endmacro %}
