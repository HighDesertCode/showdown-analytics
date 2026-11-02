-- Each previewed Pokémon matched to reference.species. Showdown IDs drop the "-*" of a form the preview hides
-- ("Urshifu-*" matches Urshifu, flagged form_hidden), and a cosmetic form reference.species doesn't list
-- ("Gastrodon-East") matches its base species.
SELECT
    pokemon.replay_id,
    pokemon.side,
    pokemon.slot,
    pokemon.species AS previewed_species,
    COALESCE(species.species_id, base_species.species_id) AS species_id,
    pokemon.species LIKE '%-*' AS form_hidden,
    pokemon.nickname
FROM {{ source('raw', 'battle_pokemon') }} AS pokemon
LEFT JOIN {{ source('reference', 'species') }} AS species ON species.showdown_id = {{ to_id('pokemon.species') }}
LEFT JOIN {{ source('reference', 'species') }} AS base_species
    ON species.species_id IS NULL
    AND base_species.showdown_id = {{ to_id("SPLIT_PART(pokemon.species, '-', 1)") }}
