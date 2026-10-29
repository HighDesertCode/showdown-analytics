-- Every chaos Pokémon's ability weight total is positive, since each option share in api divides by it.
-- Returns each Pokémon whose total is zero or negative; a missing total fails the not_null test instead.
SELECT chaos_pokemon_id, source_file_id, pokemon_name, ability_weight_total
FROM {{ ref('stg_chaos_pokemon') }}
WHERE ability_weight_total <= 0
