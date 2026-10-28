-- Abilities from Pokémon Showdown.
SELECT
    ability.ability_id,
    ability.showdown_id AS ability,
    ability.name AS ability_name,
    ability.short_description,
    ability.nonstandard
FROM {{ source('reference', 'ability') }} AS ability
