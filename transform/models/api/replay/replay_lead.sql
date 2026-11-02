-- How often each Pokémon leads a team of its type in rated public replays, by Elo band, and how often those teams
-- win. lead_share is leads / teams of that type and band that sent out a lead (a battle forfeited at team
-- preview has none), so shares sum to 1 per type and band.
WITH lead AS (
    SELECT DISTINCT ON (replay_id, side)
        replay_id,
        side,
        species_id
    FROM {{ ref('replay_battle_event') }}
    WHERE event = 'switch' AND turn = 0
    ORDER BY replay_id, side, seq
),

team_lead AS (
    SELECT
        battle.format,
        battle.report_month,
        side.elo_band,
        side.team_type,
        lead.species_id,
        side.result
    FROM lead
    INNER JOIN {{ ref('replay_battle_side') }} AS side ON side.replay_id = lead.replay_id AND side.side = lead.side
    INNER JOIN {{ ref('replay_battle') }} AS battle ON battle.replay_id = lead.replay_id
    WHERE battle.rated AND side.team_type IS NOT NULL
),

lead_count AS (
    SELECT
        format,
        report_month,
        elo_band,
        team_type,
        species_id,
        COUNT(*) AS lead_count,
        COUNT(*) FILTER (WHERE result = 'win') AS win_count
    FROM team_lead
    GROUP BY format, report_month, elo_band, team_type, species_id
)

SELECT
    lead_count.format,
    lead_count.report_month,
    lead_count.elo_band,
    lead_count.team_type,
    species.species_id,
    species.showdown_id AS species,
    species.name AS species_name,
    lead_count.lead_count,
    SUM(lead_count.lead_count) OVER scope AS team_count,
    TRIM_SCALE(ROUND(lead_count.lead_count / SUM(lead_count.lead_count) OVER scope, 10)) AS lead_share,
    lead_count.win_count,
    TRIM_SCALE(ROUND(lead_count.win_count::NUMERIC / lead_count.lead_count, 10)) AS win_rate
FROM lead_count
INNER JOIN {{ source('reference', 'species') }} AS species ON species.species_id = lead_count.species_id
WINDOW scope AS (PARTITION BY lead_count.format, lead_count.report_month, lead_count.elo_band, lead_count.team_type)
