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

## Endpoints

The endpoints are grouped by where their data comes from. All of them are versioned under `/v1`, so a future change can't break clients built on this version.

| Group | Answers questions like |
| --- | --- |
| Smogon statistics | Which Pokémon are most used on Water teams? What does Swampert usually carry, and what checks it? How does Water fare against Ground? |
| Replay statistics | How often do Water teams win against Ground in public replays? What do Fire teams lead with? How much damage does Stealth Rock do? |
| Battles | Which battles did a player upload? What happened in a given battle, turn by turn? |
| Reference data | What are a Pokémon's base stats? What does a move or item do? |

Filters left out get sensible defaults, such as the latest month and the 1630 baseline, and accept names as well as Showdown IDs (`Ninetales-Alola` or `ninetalesalola`). Long lists are returned in pages.

## Responses

Every response has the same shape:

- **Scope:** what the data covers (for example, the month, baseline, and team type), including any defaults the API filled in, and whether it comes from Smogon, from replays, or from reference data.
- **Sources:** the Smogon files behind the data, with links to where they are published.
- **Data:** the statistics themselves.
- **Page:** for long lists, which rows were returned and how many there are in all.

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
