{{ config(indexes=[{'columns': ['format', 'report_month', 'species']}]) }}
-- The index serves the API's search by attacker, which filters on species rather than the primary key's species_id.
-- Direct hits from each Pokémon's moves on the opposing Pokémon in rated public replays, by the attacker's Elo
-- band. Damage is a percent of the target's max HP, capped at the HP it had left, so a strong move's mean
-- understates it. Each hit of a multi-hit move counts separately. Recoil, items, abilities, and self-inflicted
-- damage (Substitute, Belly Drum) are left out.
SELECT
    battle.format,
    battle.report_month,
    side.elo_band,
    species.species_id,
    species.showdown_id AS species,
    species.name AS species_name,
    move.move_id,
    move.showdown_id AS move,
    move.name AS move_name,
    COUNT(*) AS hit_count,
    TRIM_SCALE(ROUND(AVG(damage.damage_percent), 10)) AS mean_damage_percent,
    COUNT(*) FILTER (WHERE damage.hp_after_percent = 0) AS knockout_count
FROM {{ ref('replay_battle_event') }} AS damage
INNER JOIN {{ ref('replay_battle_event') }} AS move_used
    ON move_used.replay_id = damage.replay_id AND move_used.seq = damage.caused_by_seq
INNER JOIN {{ ref('replay_battle_side') }} AS side
    ON side.replay_id = move_used.replay_id AND side.side = move_used.side
INNER JOIN {{ ref('replay_battle') }} AS battle ON battle.replay_id = damage.replay_id
INNER JOIN {{ source('reference', 'species') }} AS species ON species.species_id = move_used.species_id
INNER JOIN {{ source('reference', 'move') }} AS move ON move.showdown_id = {{ to_id('move_used.detail') }}
WHERE
    battle.rated
    AND damage.event = 'damage'
    AND damage.source IS NULL
    AND damage.damage_percent IS NOT NULL
    AND damage.side <> move_used.side
    AND move_used.event = 'move'
GROUP BY
    battle.format,
    battle.report_month,
    side.elo_band,
    species.species_id,
    species.showdown_id,
    species.name,
    move.move_id,
    move.showdown_id,
    move.name
