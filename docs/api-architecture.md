# API Architecture

Showdown Analytics will publish its competitive Pokémon statistics through a free, read-only web API, starting with Gen 9 Monotype. It is built for people and for AI agents, such as ChatGPT, that answer questions about the metagame. The API is in development; this page describes what it will offer.

## Data

| Data | Source | Updated |
| --- | --- | --- |
| Usage statistics | Smogon's monthly reports: usage, movesets, teammates, checks and counters, leads, metagame tags, and type matchups | Monthly, once Smogon publishes them |
| Replay statistics | Public Pokémon Showdown replays: type matchups, leads, and move and hazard damage | Daily |
| Battles | Each public replay, turn by turn | Daily |
| Reference data | Pokémon, types, abilities, moves, items, and natures from Pokémon Showdown | When Showdown adds or changes them |

See [Database Architecture](database-architecture.md) for how the data is collected and what each table holds.

## Reading the Numbers

Every statistic says what it measures and where it came from:

- **Scope:** usage statistics are scoped by format, month, rating baseline, and team type. Smogon's 1630 and 1760 baselines weight each team by its player's rating; they are not rating cutoffs.
- **Shares:** proportions run from 0 to 1, and each one states its denominator.
- **Sources:** every Smogon statistic links to the report file it came from.
- **Samples:** replay statistics describe the battles players chose to upload, not the whole ladder, so they are kept apart from Smogon's statistics. Their Elo bands are not comparable to Smogon's baselines.
- **Unknowns:** missing data is reported as unknown, not as zero, and anything inferred is marked as inferred.

## Access

The API will be public and require no account. It will be documented with an OpenAPI schema, so AI agents and other clients can discover its endpoints. Requests are rate limited to keep the service available for everyone.

The API only reads published statistics. It cannot change data, and private research data is never reachable through it.
