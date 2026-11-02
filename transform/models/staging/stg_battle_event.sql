-- One row per game event, with its Pokémon and target matched to reference.species the way the battle's
-- Pokémon are (a cosmetic form such as "Vivillon-Tundra" matches its base species). The log line is left out.
SELECT
    event.replay_id,
    event.seq,
    event.turn,
    event.side,
    event.pokemon,
    COALESCE(species.species_id, base_species.species_id) AS species_id,
    event.event,
    event.detail,
    event.target_side,
    event.target_pokemon,
    COALESCE(target_species.species_id, target_base_species.species_id) AS target_species_id,
    event.damage_percent,
    event.hp_after_percent,
    event.healed_percent,
    event.caused_by_seq,
    event.source,
    event.source_inferred
FROM {{ source('raw', 'battle_event') }} AS event
LEFT JOIN {{ source('reference', 'species') }} AS species ON species.showdown_id = {{ to_id('event.pokemon') }}
LEFT JOIN {{ source('reference', 'species') }} AS base_species
    ON species.species_id IS NULL
    AND base_species.showdown_id = {{ to_id("SPLIT_PART(event.pokemon, '-', 1)") }}
LEFT JOIN {{ source('reference', 'species') }} AS target_species
    ON target_species.showdown_id = {{ to_id('event.target_pokemon') }}
LEFT JOIN {{ source('reference', 'species') }} AS target_base_species
    ON target_species.species_id IS NULL
    AND target_base_species.showdown_id = {{ to_id("SPLIT_PART(event.target_pokemon, '-', 1)") }}
