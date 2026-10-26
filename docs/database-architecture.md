# Database Architecture

## Deployed Database

| Setting | Current configuration |
| --- | --- |
| Cluster | `showdown-analytics-db-cluster` |
| Provider | DigitalOcean Managed Databases |
| Engine | PostgreSQL 18 |
| Region | `sfo2` |
| Node size | `db-s-1vcpu-1gb`: 1 vCPU, 1 GB RAM |
| Nodes | 1 |
| Storage | 10 GiB (10,240 MiB) |
| Status | Online |
| Project database | `showdown-database` |
| Project user | `showdown-analyst` |
| Default database | `defaultdb`; not used by the project |
| Networking | Assigned VPC; public and private connection endpoints available |
| Connection encryption | SSL required according to cluster metadata |
| Trusted sources | Droplet `tailscale-virtual-machine` (ID `612370828`) |

`showdown-database` was recreated empty on October 25, 2026. The `reference` schema was created from `sql/` that day and loaded on October 26, 2026 by `pipelines load-reference` from Showdown's current data files; a rerun inserted no rows. Backups and Terraform adoption remain unverified.

| `reference` table | Rows | Notes |
| --- | ---: | --- |
| `type` | 18 | Standard types; Tera-only Stellar excluded |
| `ability` | 321 | With short descriptions |
| `species` | 1,462 | Excludes cosmetic forms and `Custom` entries such as MissingNo. |
| `species_ability` | 3,191 | Slots `0`, `1`, and `H`; special-event slot `S` excluded |
| `move` | 954 | With target and short descriptions |
| `move_effect` | 440 | Guaranteed and secondary effects, including stat stages and field effects |
| `item` | 587 | With berry flag and short descriptions |
| `nature` | 25 | Neutral natures have no stat changes |

Removed or non-Gen 9 entries remain, flagged in `nonstandard` (e.g. `Past`, `CAP`). The data reflects Showdown at load time; no source revisions or archives are recorded yet.

## Schemas

| Schema | Responsibility | Core entities |
| --- | --- | --- |
| `reference` | Canonical Pokémon data and historical rules | Deployed: types, species/forms, abilities, moves, move effects, items, natures. Planned: aliases, format versions |
| `sources` | Provenance and processing history | Source artifacts, revisions, ingestion runs, processing outcomes |
| `statistics` | Published monthly aggregates | Snapshots, usage, options, spreads, teammates, counters, metagame tags, type matchups |
| `replays` | Public battle evidence | Battles, sides, Pokémon instances, ordered events, observations |
| `research` | Private competitive records | Versioned teams, team members, personal battles, notes, hypotheses |

Core relationships by domain; supporting tables and columns are omitted. Relationships are proposed and will be finalized in migrations.

### Monthly Statistics

| Entity | Relationship |
| --- | --- |
| `stats_snapshot` | Groups zero or more `pokemon_usage` records; each usage record belongs to one snapshot. |
| `species` | Identifies the Pokémon in zero or more usage records; each usage record references one species. |
| `source_artifact` | Supports zero or more usage records; each usage record references one artifact. |

### Public Replays

| Entity | Relationship |
| --- | --- |
| `source_artifact` | Documents zero or more battles; each battle references one artifact. |
| `battle` | Contains zero or more `battle_pokemon` records; each Pokémon instance belongs to one battle. |
| `species` | Identifies zero or more battle Pokémon; each instance optionally references one species when known. |

### Private Research

| Entity | Relationship |
| --- | --- |
| `team_version` | Contains zero or more team members and links to zero or more personal battles. |
| `team_member` | Belongs to one team version and references one species. |
| `personal_battle` | References one team version and optionally one public replay battle. |
| `battle` | May be linked to zero or more personal battle records. |

In the proposed design, public schemas have no dependency on private research. Monthly aggregates and replays share reference entities without an assumed battle-level join. Their table definitions are covered by later M1 issues.

## Data Conventions

The planned data model follows these conventions:

| Area | Representation |
| --- | --- |
| Names and identity | Explicit schema names, singular `snake_case` tables, and `bigint` identity keys with matching foreign keys. Natural keys have uniqueness constraints. Showdown IDs, aliases, display names, and original labels remain available; forms have distinct identities. |
| Time and versions | Instants use `timestamptz` and UTC interchange. Report months use a first-of-month `date`. Battle, upload, and retrieval times are separate. Reference and ruleset versions retain source revisions and known effective dates. |
| Metrics and scope | Snapshots are scoped by month, format, baseline, overall/type population, and revision. Raw counts are integers; weights are fractional. Proportions have explicit denominators. Usage and moveset counts remain separate, as do replay results and ladder aggregates. |
| Missingness and provenance | Unknown scalar values are `NULL`; measured zero remains zero. Availability and processing states describe missing reports. Observations and inferences are distinct. Facts link to versioned source artifacts and exact archived files. |
| Integrity and queries | Foreign keys, required fields, uniqueness rules, and metric-specific checks enforce consistency. Common joins and filters have indexes. Typed columns hold analytical facts; JSONB holds flexible source/event details. Marginal statistics do not represent complete observed sets. |

## Infrastructure and Access

Managed PostgreSQL is the deployed relational store. DigitalOcean Spaces archival and App Platform deployment remain planned. The future Streamlit application consumes the read-only API rather than connecting directly to PostgreSQL; application setup follows the API work.

The deployed access Droplet is `tailscale-virtual-machine`, with private address `10.120.0.4`, in the database's `default-sfo2` VPC (`10.120.0.0/20`). It is a database trusted source and has joined the tailnet. Private connectivity through the subnet router has been verified.

The intended connection path is Mac → Tailscale subnet router → PostgreSQL private endpoint. Approved routes and tailnet access rules limit destinations and ports. Default subnet-router source NAT makes forwarded connections originate from the router; database TLS still verifies the database hostname. Sources: [Tailscale subnet routers](https://tailscale.com/kb/1019/subnets) and [DigitalOcean PostgreSQL connectivity](https://docs.digitalocean.com/products/databases/postgresql/how-to/connect/).

The intended access model separates migration, ingestion, public read-only, and private-research roles. Public readers have no access to `research`. Managed connections use restricted network paths and TLS with certificate verification; these controls remain subject to implementation and validation. Currently, `doadmin` owns the `reference` objects, and `showdown-analyst` has `USAGE` on the schema and `SELECT`, `INSERT`, and `DELETE` (no `UPDATE`) on its tables, including future tables through default privileges. The grant file `sql/permissions/showdown_analyst.sql` is applied but not yet committed.

| Owner | Managed changes |
| --- | --- |
| Terraform | Supported cloud resources, networking, service configuration, and infrastructure drift |
| SQL migrations | Schemas, tables, relationships, constraints, indexes, database roles, and grants |

The Terraform workflow adopts manually created services through matching resource definitions and `terraform import`. A refreshed plan showing no changes establishes configuration parity for managed attributes. Remote state is kept outside Git with restricted access and a documented locking approach. Unsupported resources and cloud-managed database users have explicit ownership to prevent conflicts with SQL migrations. Terraform adoption is planned; it was not verified during this inspection.

SQL lives in `sql/create/`, `sql/index/`, and `sql/permissions/`, one file per table or role, and is run manually as `doadmin` in foreign-key order (listed in `tests/pipelines/conftest.py`). Migration tooling is not yet in place.
