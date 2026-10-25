# Pokémon Showdown Monotype Analytics Research Report

Research date: October 23, 2026. Scope: public Smogon monthly statistics, Pokémon Showdown reference data, public battle replays, and a proposed PostgreSQL foundation for LLM-assisted analytics. This report is research and design guidance; it does not implement an ingestion pipeline, database, or ChatGPT integration.

PostgreSQL is a good fit for this project. The proposed system combines three complementary datasets: monthly Smogon statistics, versioned Pokémon and format reference data, and individual battle replays. Together they support usage trends, team-building research, type matchup analysis, and retrieval of battle examples.

The central design requirement is preserving what each observation measures. Usage across all Monotype teams, usage within Water teams, and win rate within collected replays have different populations and denominators. They must remain distinguishable throughout ingestion, storage, queries, and LLM answers.

The research included directory inspection, retrieval of September 2026 report files and JSON, a public Monotype replay sample, and review of Smogon's current statistics-generation implementation. Recommendations below are proposed design choices, distinguished from source observations. Mutable repository links describe the implementation inspected during research, not proof of the exact code revision that generated every historical report.

**The monthly archive contains several report families.** Smogon's `/stats/` site is a published file archive. Paths identify a month, format, statistical weighting baseline, and sometimes a team-type filter. This archive is separate from Showdown's replay and ladder APIs. Sources: [September 2026 directory](https://www.smogon.com/stats/2026-09/) and [Showdown web API documentation](https://github.com/smogon/pokemon-showdown-client/blob/master/WEB-API.md).

| Location within a month | Contents | Example analytical question |
| --- | --- | --- |
| `gen9monotype-1630.txt` | Pokémon rankings, weighted usage, raw counts, and real usage | Which Pokémon are most common overall? |
| `leads/` | Opening Pokémon frequencies | What usually leads? |
| `metagame/` | Team-type, playstyle, and weather tags; stalliness summary | How common are Water teams or rain? |
| `moveset/` | Human-readable option and teammate summaries | What does a typical Pokémon carry? |
| `chaos/` | Detailed machine-readable moveset statistics in JSON | What should the ingestion pipeline consume? |
| `monotype/` | Reports filtered to teams sharing a particular type | What is common specifically on Water teams? |
| `monotype/matchupcharts/` | Type-versus-type outcomes and published type scores | How did Water perform against Ground? |

The Monotype subtree repeats the `chaos`, `leads`, `metagame`, and `moveset` report families. For example, `gen9monotype-monowater-1630` identifies the Gen 9 Monotype format, a Water-team filter, and the 1630 baseline. [Monotype directory](https://www.smogon.com/stats/2026-09/monotype/)

Treat `gen9monotype` and `gen9nationaldexmonotype` as separate formats. Discover available months, formats, baselines, and files from the archive instead of assuming identical coverage throughout its history. A directory's modification timestamp is not the statistical period.

**The rating numbers are weighting baselines.** Four relevant published baselines are `0`, `1500`, `1630`, and `1760`. They are not mutually exclusive Elo brackets. Smogon's calculation uses Glicko rating and uncertainty to estimate the probability that underlying skill exceeds a baseline. The current implementation gives zero weight when uncertainty exceeds 100 and the baseline exceeds 1500. A battle can therefore contribute to multiple reports with different weights. [Current weighting implementation](https://github.com/smogon/usage-stats/blob/main/src/common.ts)

| Baseline | Practical interpretation |
| --- | --- |
| `0` | Essentially unweighted statistics, still subject to the source's processing rules |
| `1500` | Weighted view using the lower baseline |
| `1630` | Stronger emphasis on higher-skill play |
| `1760` | Stronger emphasis still, potentially with less statistical support |

Recommendation: collect all four and initially use `1630` as the default analytical view. Always display the baseline. This default is a product choice, not a claim that one baseline is universally correct. Never add the four reports together or label `1760` as all battles played by people with Elo above 1760.

**The `chaos/` files are a primary ingestion source.** They contain detailed aggregate statistics, not battle logs or a separate battle format. The inspected Water file includes report metadata and per-species statistics. Sources: [actual Water JSON](https://www.smogon.com/stats/2026-09/monotype/chaos/gen9monotype-monowater-1630.json) and [overall JSON](https://www.smogon.com/stats/2026-09/chaos/gen9monotype-1630.json).

| Field | Interpretation |
| --- | --- |
| `info.metagame` | Format identifier |
| `info.cutoff` | Weighting baseline |
| `info.cutoff deviation` | Source-provided metadata; preserve verbatim |
| `info.team type` | Team-type filter, or null for the overall report |
| `info.number of battles` | Published report battle count; not necessarily subgroup size |
| `data[species].usage` | Published usage proportion for the selected population |
| `Raw count` | Unweighted appearances in the moveset dataset |
| `Abilities`, `Items`, `Moves` | Weighted totals for each option |
| `Spreads` | Weighted totals for nature-and-EV combinations |
| `Teammates` | Weighted teammate co-occurrences |
| `Checks and Counters` | Encounter-based statistics, where available |
| `Viability Ceiling` | A summary derived from users' GXE values |
| `Tera Types`, `Happiness` | Additional fields with format-dependent relevance |

Option values require normalization. For items, divide an item's weight by the Pokémon's total ability weight. Move inclusion uses that same Pokémon denominator, rather than the sum of all move weights. Keep the original spread label: the generator can transform EV representations, and the aggregate spread is not a complete team export. The JSON's viability tuple and check/counter fields are source-defined summaries, not Pokémon win rates. [Current moveset generator](https://github.com/smogon/usage-stats/blob/main/src/batchMovesetCounter.ts)

For Water Swampert in the inspected sample, the Leftovers weight is approximately `848.989`, and total ability weight is `1429.394`. Their ratio is **59.395%**, matching the text report. Dividing by the raw count would produce an incorrect percentage. Four moves per set mean move inclusion percentages can total approximately 400%. Preserve original weights, denominators, and derived proportions. [Water moveset report](https://www.smogon.com/stats/2026-09/monotype/moveset/gen9monotype-monowater-1630.txt)

The chaos JSON is useful but does not replace every report family. Published lead and metagame information still warrants separate ingestion. The ecosystem's output documentation also discusses this distinction; use actual Smogon files and its current generator as the authority for contemporary field shapes, rather than assuming a related library's proposed output is identical. [Stats output documentation](https://github.com/pkmn/stats/blob/main/stats/OUTPUT.md)

**Several statistical distinctions change the answers.**

| Distinction | Research observation | Storage implication |
| --- | --- | --- |
| Overall versus type-specific usage | Swampert is 5.78601% overall and 65.06545% within Water teams in September's 1630 reports | Include an explicit team-type scope |
| Raw versus real usage | Raw counts team appearances; real counts Pokémon that appeared in battle | Store the published measures separately |
| Header versus subgroup count | Overall and Water reports both report 63,572 total battles | Do not interpret the Water header as Water-team count |
| Usage versus moveset count | Water Swampert has 4,297 raw usage appearances but 4,603 moveset appearances | Keep distinct count fields and provenance |
| Missing versus zero | Detailed reports have reporting thresholds and may omit species | Preserve missingness instead of manufacturing zeros |
| Marginal versus joint distributions | Item, move, and spread frequencies do not identify complete individual sets | Do not synthesize a supposedly observed set by combining popular options |

Sources: [overall usage](https://www.smogon.com/stats/2026-09/gen9monotype-1630.txt), [Water usage](https://www.smogon.com/stats/2026-09/monotype/gen9monotype-monowater-1630.txt), [Water movesets](https://www.smogon.com/stats/2026-09/monotype/moveset/gen9monotype-monowater-1630.txt), and [Smogon's raw/real explanation](https://www.smogon.com/forums/threads/official-smogon-university-usage-statistics-discussion-thread-mk-2.3508502/).

The raw-count discrepancy is verified; this research did not establish a complete historical explanation for every difference across report families. Preserve the distinction instead of enforcing equality or silently correcting a source. Real usage percentages also have their own source normalization and should not be relabeled as the probability that a roster member entered battle.

Monthly files do not provide a general species-level battle win-rate table. Neither usage nor viability ceiling should be presented as one. Type scopes can overlap in edge cases where a team shares more than one type, so do not assume every type-filtered report forms a disjoint population.

**Metagame tags and matchup outcomes need their own models.** The inspected metagame file mixes type shares with tags such as `rain`, `balance`, and `voltturn`. Tags may overlap. Water's **8.59354%** describes weighted prevalence, not win rate. The stalliness histogram is a rounded text visualization; reconstructing exact bin populations from its bars is not possible. [Metagame sample](https://www.smogon.com/stats/2026-09/metagame/gen9monotype-1630.txt)

Playstyle tags are algorithmic classifications based on team characteristics, not universally agreed human labels. Retain original tag names, including historical terminology such as `hail`. If replay teams are classified independently, record the classifier and version rather than presenting those labels as identical to Smogon's output. [Team classification implementation](https://github.com/smogon/usage-stats/blob/main/src/TA.ts)

In the type matchup chart, numeric cells represent weighted wins for the row type against the column type. Percentages use the opposing directional wins, with a denominator floor in the current implementation. Outcomes use the smaller player weight. Mirror-match percentages remain zero rather than representing genuine 0% performance. [Current report generator](https://github.com/smogon/usage-stats/blob/main/src/StatCounter.ts)

The September chart reports **72.636% for Water against Ground** at the 1630 baseline. This is a weighted aggregate across players and team variations, not a prediction for every Water team. Store `ViabilityScore` as a published source-defined score, distinct from win rate or community viability rankings. This research does not certify its comparability across historical generator revisions. [Matchup sample](https://www.smogon.com/stats/2026-09/monotype/matchupcharts/gen9monotype-matchup_chart-1630.txt)

Empty check/counter data is not evidence that a Pokémon has no counters. In the inspected Water chaos file, every species had an empty check/counter object, while the overall file contained entries. Represent availability explicitly. Older ecosystem documentation also describes different check/counter representations; parsers should detect and validate the source shape.

**Reference data should come from Showdown's ecosystem.** Public API documentation links Pokédex and move JSON. Showdown's Dex exposes species, forms, items, abilities, natures, and generation-specific information. Sources: [public resources](https://github.com/smogon/pokemon-showdown-client/blob/master/WEB-API.md), [Pokédex JSON](https://play.pokemonshowdown.com/data/pokedex.json), [move JSON](https://play.pokemonshowdown.com/data/moves.json), and [Dex documentation](https://github.com/smogon/pokemon-showdown/blob/master/sim/DEX.md).

| Reference data | Analytical purpose |
| --- | --- |
| Species and forms | Distinguish regional forms, alternate forms, and base species |
| Types and effectiveness | Explain defensive and offensive coverage |
| Base stats | Compare speed tiers and Pokémon characteristics |
| Moves, items, abilities, natures | Resolve identifiers and explain mechanics |
| Learnsets and legality | Check whether a proposed set is valid |
| Format rules and bans | Interpret data under the applicable rules |
| Aliases | Resolve informal names and source naming differences |

Recommendation: use stable Showdown identifiers with display names and original source labels. A National Pokédex number alone is insufficient because forms share numbers. Keep source aliases distinct from the identity rules used to aggregate cosmetic or battle forms.

Version reference resources and rules. Current definitions cannot reliably explain an older month. The current Gen 9 Monotype format includes Terastal Clause, and the inspected replay explicitly prohibits Terastallization. The presence of a `Tera Types` field does not prove that mechanic was available. [Format definitions](https://github.com/smogon/pokemon-showdown/blob/master/config/formats.ts)

Historical rule snapshots may require repository history and additional validation. A monthly report can span a mid-month rule change, so do not assign one exact ruleset to all of its observations without evidence. Store both the applicable interval and uncertainty where necessary.

**Replays provide battle-level evidence with different coverage.**

| Resource | URL pattern |
| --- | --- |
| Format search | `https://replay.pokemonshowdown.com/search.json?format=gen9monotype` |
| Replay JSON | `https://replay.pokemonshowdown.com/{replay-id}.json` |
| Replay log | `https://replay.pokemonshowdown.com/{replay-id}.log` |

The documented search returns up to 51 results, using the extra result to indicate another page. The `before` cursor uses upload time; the older `page` parameter is discouraged. Input logs are documented for automatically generated-team formats, not as a source of full Monotype teams. [Replay API documentation](https://github.com/smogon/pokemon-showdown-client/blob/master/WEB-API.md)

The retrieved search returned 51 results. The inspected replay contains format ID, players, upload time, a replay rating, and a battle log. Its log includes preview species, individual Elo values, moves, switches, damage, revealed abilities, and outcome. [Inspected replay JSON](https://replay.pokemonshowdown.com/gen9monotype-2703725750.json)

Uploaded replays are a selected sample. Do not assume search exposes every ladder battle or that collected replay win rates represent the full ladder. Missing or inaccessible replays should be recorded as retrieval outcomes, not silently dropped from collection accounting.

Public logs generally cannot reveal unobserved moves, starting items, abilities, EVs, or IVs. Keep unknown values unknown. Separate directly observed facts from deductions and aggregate priors. Preserve upload time separately from battle timestamps, the replay rating separately from individual player Elo, and both separately from Smogon's Glicko baseline.

Battle events are ordered protocol messages. An identifier such as `p1a` represents a battlefield position, and nicknames are not necessarily species. Transformations and Illusion require identity handling. Record the original event sequence and line so derived facts can be audited. [Simulator protocol](https://github.com/smogon/pokemon-showdown/blob/master/sim/SIM-PROTOCOL.md)

**The proposed PostgreSQL design has four logical layers.** These are conceptual tables; implementation can be phased.

| Layer | Suggested tables | Row meaning |
| --- | --- | --- |
| Source archive | `source_artifact`, `ingestion_run` | A fetched file revision or collection run |
| Reference | `species`, `species_version`, `move`, `item`, `ability`, `format_version`, `entity_alias` | An entity or historical definition |
| Monthly statistics | `stats_snapshot`, `pokemon_usage`, `pokemon_option_usage`, `pokemon_spread_usage`, `pokemon_teammate`, `pokemon_counter`, `metagame_tag`, `type_matchup` | An explicitly scoped aggregate observation |
| Battles | `battle`, `battle_side`, `battle_pokemon`, `battle_event`, `pokemon_observation` | A replay, participant, Pokémon instance, event, or revealed fact |

The key monthly dimensions are **month + format + baseline + team-type scope + source revision**. For example: `2026-09 / gen9monotype / 1630 / Water / revision 1`. Treat all teams as an explicit scope. A snapshot groups compatible reports, while every fact retains a reference to its own source artifact and metric definition.

| Table | Essential contents |
| --- | --- |
| `source_artifact` | URL, retrieval time, content hash, exact archive location, available HTTP metadata, parser version, retrieval and parse status |
| `ingestion_run` | Run start/end, requested coverage, outcomes, validation findings, resumable progress |
| `stats_snapshot` | Month, format, baseline, scope, reported battle count, completeness, revision |
| `pokemon_usage` | Species, rank, published weighted proportion, raw usage count/proportion, real usage count/proportion |
| `pokemon_option_usage` | Species, option category, option ID, source weight, denominator, derived proportion |
| `pokemon_spread_usage` | Original spread label, nature, six EV values, weight, proportion |
| `pokemon_teammate` | Focal species, teammate, source value, interpretation and denominator where valid |
| `pokemon_counter` | Focal species, opponent, encounter weight, reported probability, uncertainty, availability |
| `metagame_tag` | Original tag, tag category, published proportion |
| `type_matchup` | Row type, opponent type, directional weighted wins, published percentage, mirror flag |
| `battle` | Replay ID, format, upload/battle timestamps, rated status, result, turn count, original metadata, parsing status |
| `battle_side` | Player, side, observed rating, result, inferred team type and inference method |
| `battle_pokemon` | Stable internal instance, side, preview/observed identity, form history and identification status |
| `battle_event` | Battle ID, sequence, turn, event type, raw line, parsed payload |
| `pokemon_observation` | Revealed fact, value, supporting event, observation/inference method and timing |

Retain original and derived values separately. Use a consistent internal proportion scale of 0–1 for probabilities and percentages, but do not constrain every field named usage to that range without validating its definition and source. Counts should be integer types where truly raw; weighted totals require fractional storage. Use timezone-aware timestamps for instants and an explicit month representation for reporting periods.

For items and abilities in replays, distinguish original, acquired, copied, consumed, and inferred values where supported. A stolen item must not automatically become evidence of the starting set. Preserve battle outcome as win, loss, tie, or unknown; do not manufacture a loss from an incomplete log. Keep ladder, tournament, challenge, and other provenance distinct when identifiable.

Monthly aggregates and replay facts share reference dimensions, but do not have a proven battle-level join. A replay can be contextualized by a nearby monthly report; it cannot be claimed as one of that report's underlying battles solely because its format and month match.

**Use typed relational data and JSONB together.** Keep exact source bytes in an archive, parsed flexible payloads in JSONB where useful, and frequently queried metrics in typed relational columns. JSONB supports indexing but does not preserve original formatting or key order, so it is not a substitute for the exact file. [PostgreSQL JSON documentation](https://www.postgresql.org/docs/current/datatype-json.html)

Initially index snapshot dimensions, species joins, replay IDs, battle dates, and event order within a battle. Add targeted option and matchup indexes based on real queries. Avoid indexing every JSON field or partitioning every table in advance. Battle events are a likely later partitioning candidate if volume justifies it.

Materialized views can accelerate repeated summaries, but their persisted results need refreshes and freshness metadata. [PostgreSQL materialized views](https://www.postgresql.org/docs/current/rules-materializedviews.html)

**LLM access should use a documented analytical interface.** PostgreSQL storage alone does not connect ChatGPT. A later integration must expose database-backed tools or approved read-only queries. This report proposes the interface but does not choose or configure a particular ChatGPT integration.

The intended flow is: question → resolve format, dates, baseline and scope → query PostgreSQL → return values, definitions and sources → generate an explanation.

Useful initial capabilities include usage trends, common options within a type, baseline comparisons, type matchup results, replay search, and retrieval of supporting turns. Each response should carry the reporting period, population, baseline, denominator, source URL, freshness, and relevant sample limitations. Use bounded results and documented views. Treat player names and replay chat as data rather than instructions to the assistant.

For example, a response to an ambiguous usage question could state: “In September 2026, at the 1630 weighting baseline, Swampert appeared on 65.07% of Water teams, compared with 5.79% overall.” The answer should expose the chosen scope rather than leaving the user to infer it.

A metric dictionary should define usage, real usage, weighted wins, collected-sample win rate, revealed moves, and missingness. A source registry should describe coverage and revision history. SQL should calculate numerical answers. Embeddings may later help retrieve written analyses or battle summaries, but they should not replace structured aggregation.

| Question | Evidence available |
| --- | --- |
| Which Pokémon are gaining usage on Steel? | Monthly type-specific usage |
| Which items are common on Water Greninja? | Type-specific chaos statistics |
| How did Water perform against Ground? | Published type matchup charts |
| Find replays where a Pokémon led | Parsed replay logs |
| How often did my collected teams win? | Replay results, scoped to the collected sample |
| What complete set or six-Pokémon team is most successful? | Requires linked complete team/outcome data; monthly marginals are insufficient |
| Why did a turn lose the battle? | Replay evidence plus interpretation, limited by hidden information |
| What is objectively the best team? | Not established by these sources alone |

Do not average monthly percentages blindly. Exact combined-period values require compatible denominators. Do not manufacture confidence intervals from weighted totals alone: published aggregates may lack the information required for defensible uncertainty estimates. Association also does not establish that an item, Pokémon, or team choice caused a win.

**The recommended starting scope is Gen 9 Monotype, all 18 types, all four baselines, and 12 complete months.** Collect overall and type-specific chaos, usage, leads, metagame, and matchup reports. Archive moveset text for validation. Where every family exists, five report families × 19 scopes × four baselines, plus four matchup charts, gives approximately **384 files per month**. This is a file-count estimate, not a storage-size or completeness guarantee.

Begin replay discovery alongside monthly ingestion. Future collection cannot guarantee recovery of a complete historical replay population. Use modest request concurrency, retries and backoff, source caching, replay-ID deduplication, and resumable checkpoints. Validate timestamp pagination around ties; do not assume a simple cursor implementation guarantees exhaustive discovery. Revisit recent archive periods for corrected or replaced files, recording new content hashes as revisions.

The proposed sequence is:

1. Validate one complete month. Confirm identifiers, units, normalization, report-specific counts, missingness, and revisions.
2. Backfill monthly reports through discovery of actual files.
3. Add incremental public replay collection with coverage and failure accounting.
4. Parse battle summaries first: participants, preview teams, leads, results, ratings, and turn counts.
5. Add detailed events and observations where they support useful questions.
6. Expose documented analytical queries before attempting detailed battle coaching.

Validation should compare JSON-derived option percentages with text reports, distinguish scope-specific denominators from repeated headers, preserve unknown identifiers for review, and check replay event order and outcome availability. Track complete, partial, failed, and not-published states independently. Never silently substitute a different month, format, or baseline when a requested file is unavailable.

The highest-value initial product answers what is common, what is changing, how types performed, and which replays illustrate those patterns, while preserving the evidence behind every number.
