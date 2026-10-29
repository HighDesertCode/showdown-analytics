-- The 18 standard types from Pokémon Showdown.
SELECT
    type.type_id,
    type.showdown_id AS type,
    type.name AS type_name
FROM {{ source('reference', 'type') }} AS type
