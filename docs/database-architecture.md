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
| Connection encryption | Required; clients use `verify-full` with DigitalOcean's CA certificate |
| Trusted sources | Droplet `tailscale-virtual-machine` (ID `612370828`) |

`showdown-database` was recreated empty on October 25, 2026. The `reference` schema was created from `sql/` that day and loaded on October 26, 2026 by `pipelines load-reference` from Showdown's current data files; a rerun inserted no rows. Backups remain unverified.

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

| Schema | Milestone | Responsibility | Core entities |
| --- | --- | --- | --- |
| `reference` | M1 (deployed) | Canonical Pokémon data and historical rules | Types, species/forms, abilities, moves, move effects, items, natures; aliases and format versions later |
| `sources` | M2 | Provenance and processing history | Source files, revisions, ingestion runs, processing outcomes |
| `statistics` | M2 | Published monthly aggregates | Snapshots, usage, options, spreads, teammates, counters, metagame tags, type matchups |
| `replays` | M4 | Public battle evidence | Battles, sides, Pokémon instances, ordered events, observations |
| `research` | M5 | Private competitive records | Versioned teams, team members, personal battles, notes, hypotheses |

Each schema's tables and relationships are designed in its milestone. Public schemas never depend on private research.

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

The connection path is Mac → Tailscale subnet router → PostgreSQL private endpoint. Approved routes and tailnet access rules limit destinations and ports. Default subnet-router source NAT makes forwarded connections originate from the router; database TLS still verifies the database hostname. Sources: [Tailscale subnet routers](https://tailscale.com/kb/1019/subnets) and [DigitalOcean PostgreSQL connectivity](https://docs.digitalocean.com/products/databases/postgresql/how-to/connect/).

`showdown-analyst` is the project's only role. It has `USAGE` on `reference` and `SELECT` and `INSERT` on its tables, including future tables through default privileges; it has no `UPDATE`, `DELETE`, DDL, or `defaultdb` access. Its grants are in `sql/permissions/showdown_analyst.sql`. `doadmin` owns all project objects and is used only to run SQL files. `PUBLIC` keeps PostgreSQL's default `CONNECT` and `TEMP` on `showdown-database` but has no `CONNECT` on `defaultdb`. Private research must never be reachable from public endpoints.

| Owner | Managed changes |
| --- | --- |
| Terraform | Supported cloud resources, networking, service configuration, and infrastructure drift |
| SQL files (`sql/`) | Schemas, tables, relationships, constraints, indexes, database roles, and grants |

Terraform adoption is planned for M6: services are imported into matching configuration until a refreshed plan reports no changes, with remote state kept outside Git.

## Applying SQL Changes

SQL is applied by hand; nothing runs it automatically.

1. Add or edit one file per table, index, or role in `sql/create/`, `sql/index/`, or `sql/permissions/`.
2. Run new files as `doadmin` in TablePlus against `showdown-database`: schemas, then tables in foreign-key order, then indexes, then permissions. `SQL_FILES` in `tests/pipelines/conftest.py` lists the create and index order, which CI uses to build its test database; permissions run last.
3. Grant files only add privileges. When removing one, run a one-time `REVOKE` and update the file to match.
4. Verify as `showdown-analyst`, then update this document's deployed state.

Changing an existing table means a one-time `ALTER` (or drop and reload, since reference data can be refetched) plus an edit to its `create` file, so the files always describe the current schema. Migration tooling (e.g. versioned migration files with a tracking table) becomes worthwhile when tables hold data that can't be reloaded, such as statistics history or private research, or when more than one environment needs the same changes.
