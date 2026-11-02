-- Damage from entry hazards (Stealth Rock and Spikes) in rated public replays, by the Elo band and inferred type
-- of the team taking it. Damage is a percent of max HP, capped at the HP left. Toxic Spikes deal no damage on
-- entry (their poison is counted as poison), and teams without an inferred type are left out.
SELECT
    battle.format,
    battle.report_month,
    side.elo_band,
    side.team_type,
    damage.source AS hazard,
    COUNT(*) AS hit_count,
    TRIM_SCALE(ROUND(AVG(damage.damage_percent), 10)) AS mean_damage_percent,
    COUNT(*) FILTER (WHERE damage.hp_after_percent = 0) AS knockout_count
FROM {{ ref('replay_battle_event') }} AS damage
INNER JOIN {{ ref('replay_battle_side') }} AS side ON side.replay_id = damage.replay_id AND side.side = damage.side
INNER JOIN {{ ref('replay_battle') }} AS battle ON battle.replay_id = damage.replay_id
WHERE
    battle.rated
    AND side.team_type IS NOT NULL
    AND damage.event = 'damage'
    AND damage.source IN ('Stealth Rock', 'Spikes')
    AND damage.damage_percent IS NOT NULL
GROUP BY battle.format, battle.report_month, side.elo_band, side.team_type, damage.source
