-- Moves from Pokémon Showdown, with their type.
SELECT
    move.move_id,
    move.showdown_id AS move,
    move.name AS move_name,
    type.showdown_id AS type,
    move.category,
    move.base_power,
    move.accuracy,
    move.pp,
    move.priority,
    move.target,
    move.short_description,
    move.nonstandard
FROM {{ source('reference', 'move') }} AS move
INNER JOIN {{ source('reference', 'type') }} AS type ON type.type_id = move.type_id
