-- Species and battle-relevant forms from Pokémon Showdown, with their types and base stats.
SELECT
    species.species_id,
    species.showdown_id AS species,
    species.name AS species_name,
    species.dex_number,
    species.base_species,
    species.forme,
    type_1.showdown_id AS type_1,
    type_2.showdown_id AS type_2,
    species.hp,
    species.atk,
    species.def,
    species.spa,
    species.spd,
    species.spe,
    species.nonstandard
FROM {{ source('reference', 'species') }} AS species
INNER JOIN {{ source('reference', 'type') }} AS type_1 ON type_1.type_id = species.type_1_id
LEFT JOIN {{ source('reference', 'type') }} AS type_2 ON type_2.type_id = species.type_2_id
