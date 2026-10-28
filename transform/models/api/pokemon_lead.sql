-- One row per Pokémon in each leads report: how often it is sent out first. Shares sum to 1 per report.
-- Smogon's lead total is left out: per-type reports repeat the overall total, so it can't serve as their denominator.
SELECT
    leads.format,
    leads.report_month,
    leads.baseline,
    leads.team_type,
    species.species_id,
    species.showdown_id AS species,
    species.name AS species_name,
    leads.rank,
    TRIM_SCALE(leads.usage_percent / 100) AS lead_share,
    leads.raw_count,
    TRIM_SCALE(leads.raw_percent / 100) AS raw_lead_share,
    leads.source_file_id
FROM {{ ref('stg_leads_pokemon') }} AS leads
INNER JOIN {{ source('reference', 'species') }} AS species ON species.species_id = leads.species_id
