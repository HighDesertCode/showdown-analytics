-- Items from Pokémon Showdown.
SELECT
    item.item_id,
    item.showdown_id AS item,
    item.name AS item_name,
    item.is_berry,
    item.short_description,
    item.nonstandard
FROM {{ source('reference', 'item') }} AS item
