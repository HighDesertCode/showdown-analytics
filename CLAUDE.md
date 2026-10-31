# Project Overview

Showdown Analytics collects and analyzes competitive Pokémon data from Smogon and Pokémon Showdown, starting with Gen 9 Monotype. It stores monthly statistics, reference data, public replays, and private research in PostgreSQL, and will expose source-attributed analytics through a public API and website (including for ChatGPT).

See `REPORT.md` for research context and data interpretation. Always preserve source provenance, reporting periods, weighting baselines, team-type scopes, and metric denominators. Keep public replay samples distinct from ladder-wide statistics, and unknown battle information distinct from inferred facts.

# Infrastructure

All services run on DigitalOcean. Notion is used separately for personal notes. This is the intended architecture; only what `docs/database-architecture.md` lists as deployed actually exists. Stay within the current milestone (M4: Pokémon Showdown Replay Collection).

- **Database:** Managed PostgreSQL. Project data goes in `showdown-database` via `showdown-analyst`; never use `defaultdb` or infer the database/user from cluster defaults. Schema changes are SQL files run manually by `doadmin`. Two project roles: `showdown-analyst` (pipelines) has `SELECT` and `INSERT` on `reference` and `raw`, with no `DELETE` or DDL and no `UPDATE` except on the progress and result columns of `raw.ingestion_run` and `raw.replay_collection_run`; `showdown-transform` (dbt) reads `reference` and `raw` and creates and owns everything in `staging` and `api`. dbt recreates `api` tables on every build, which drops one-off grants, so other roles get access to them through `ALTER DEFAULT PRIVILEGES FOR ROLE "showdown-transform"` in their permission file (`doadmin` is a member of that role). `CONNECT` on `defaultdb` is revoked from `PUBLIC`, and only the project roles can connect to `showdown-database` (`showdown-transform` also has `TEMPORARY`, for dbt's unit tests), so any new role needs an explicit `GRANT CONNECT`. The permission files name it with `current_database()`, so run them while connected to it.
- **Developer access:** Tailscale subnet router on a Droplet in the database VPC, plus trusted sources and TLS with certificate verification.
- **Scheduled ingestion:** an App Platform scheduled job, specified in `pipelines/app.yaml`, builds `pipelines/Dockerfile` from `main` and runs `pipelines update-smogon` daily at 8:00 Pacific, connecting over the database VPC. The attached database supplies the analyst's credentials and the CA certificate (`DATABASE_CA_CERT`, which `pipelines.db` writes to a file for `PGSSLROOTCERT`); `DBT_PASSWORD` is a `SECRET`. Failed runs and deployments send alert emails. The spec's placeholders are filled in only in the control panel. Change the live app from its current spec (`doctl apps spec get`, edit, `doctl apps update`) or the control panel, never from `pipelines/app.yaml`, which holds placeholders and no `DBT_PASSWORD` value, so updating from it would blank the password.
- **Planned:** a read-only FastAPI service, a Streamlit site and a public CLI that both consume only that API, and private research storage that is never reachable from public endpoints.

**Terraform:** Create services manually, write matching configuration, `terraform import`, and confirm a no-change plan before managing changes through Terraform. Keep state outside Git; never commit state, plans, credentials, or secret variable files.

**Security:** Least-privilege roles, private networking, and verified TLS. Never commit or log secrets; use environment variables and placeholder-only example files.

# Development

- **Layout:** One top-level directory per product: `pipelines/` (internal data loading; the only code that writes to `reference` and `raw`), `transform/` (the dbt project that builds `staging` and `api`), and later `api/`, `web/`, and `cli/` (the public CLI, which uses only the API). Tests mirror it under `tests/<product>/`.
- **SQL:** `sql/create/<schema>/` and `sql/index/<schema>/` hold one file per table (plus `schema.sql`), and `sql/permissions/` one file per role, run manually as `doadmin` in TablePlus (SQL keywords, functions, and types are uppercase everywhere, including dbt): `SQL_FILES` then `PERMISSION_FILES` in `tests/pipelines/conftest.py` give the order. Grant files only add privileges, so removing one needs a one-time `REVOKE`; changing a table needs a one-time `ALTER` plus an edit to its `create` file. Verify as `showdown-analyst` and update the docs' table counts. Add migration tooling once tables hold data that can't be reloaded.
- **Reference data:** Showdown's own data files are the source of truth (not PokeAPI). Loaders insert only new rows, skipping existing `showdown_id`s up front rather than using `ON CONFLICT`, and run in one transaction.
- **Smogon data:** `load-smogon <YYYY-MM> [--family <family>]` loads chaos, usage, leads, metagame, and matchup chart reports (overall and per type, at 1630 and 1760) into `raw`, committing each file separately. A file is skipped when the latest version of its URL in `raw.source_file` has the same SHA-256, so a file that reverts to earlier content is loaded again. Downloads are retried after brief failures; files that still fail are listed at the end and the command exits with status 1, so a rerun loads only those. Each run is logged in `raw.ingestion_run`, updated after every file. Parsers are strict and raise `ReportFormatError` on any unexpected shape. Raw files aren't archived; Smogon keeps them online. `update-smogon` loads the previous month: it exits without downloading when every file is already in `raw.source_file`, and with one `HEAD` request while Smogon hasn't published it; otherwise it runs `load-smogon` and then the two dbt builds below, exiting non-zero if any step fails. A loaded month isn't checked again, so rerun a republished file with `load-smogon` and a failed dbt build by hand.
- **Replays:** `collect-replays --start <YYYY-MM-DD> --end <YYYY-MM-DD>` stores the public Gen 9 Monotype replays uploaded in that window (UTC days, both included) in `raw.replay`; with no window it resumes from the newest stored replay up to now, so it fills no gaps below that replay (collect those windows explicitly), and it refuses to run on an empty table. It reads every search page first, skips stored replays and those from side servers (IDs prefixed with the server, e.g. `smogtours-`; main-server battles only), then downloads the rest oldest first, one request a second, committing each replay separately. Replays that fail to download or fail the strict checks (`ReplayFormatError`) are listed at the end and the command exits with status 1; collect the same window again to retry them. Each run is logged in `raw.replay_collection_run`.
- **Running pipelines:** `uv run --env-file .env pipelines <command>` (add `--group dbt` for `update-smogon`, which runs dbt); `.env` holds libpq `PG*` variables with `PGSSLMODE=verify-full`.
- **Tooling:** pytest, Ruff (120-character lines; rules `E`, `F`, `I`, `UP`, `B`), and ty (beta, pinned to an exact version). Before committing:

  ```bash
  uv run ruff check --fix pipelines tests/pipelines   # fixes lint issues, including sorting imports
  uv run ruff format pipelines tests/pipelines        # formats the code
  uv run ty check pipelines tests/pipelines           # type checks
  uv run pytest tests/pipelines                       # runs tests
  ```

  Database tests are skipped unless `TEST_DATABASE_URL` points at a disposable database as a superuser (CI provides one). They build the schemas as `doadmin`, run the permission files, and test as `showdown-analyst`, so a missing grant fails them; locally, run `docker run -d --rm --name sa-test-pg -e POSTGRES_PASSWORD=postgres -p 54329:5432 postgres:18` and set `TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:54329/postgres`.

- **CI:** One workflow per product and check, named `<product>-<check>.yml` (`tests`, `lint`, `type-checker`, `docker`), each triggered only by changes to that product's paths. `transform-tests.yml` sets up an empty database with `tests/transform/setup_database.py` and runs `dbt build`. `pipelines-docker.yml` builds the ingestion image from `pipelines/Dockerfile` (built from the repo root; `.dockerignore` is an allowlist, so add any new file the image needs to it), then scans it with Syft and Grype and uploads the fixable vulnerabilities as SARIF to code scanning without failing the build; it also runs on pushes to `main` and weekly, so the alerts stay current.
- **dbt:** `staging` holds views that clean each raw table once; `api` holds statistics as tables (with enforced contracts) and reference data as views (`models/api/reference/`). Shares are 0-to-1 proportions with their denominators documented. Unit tests live in `*_unit_tests.yml` next to their models. After a monthly load, build `staging` and then `api`, so a failed staging test (including the check that every month has all 77 files) leaves every `api` table untouched (`.env` also holds `DBT_USER` and `DBT_PASSWORD`):

  ```bash
  uv run --group dbt --env-file .env dbt build --project-dir transform --profiles-dir transform --select staging \
    && uv run --group dbt --env-file .env dbt build --project-dir transform --profiles-dir transform --select api
  ```

# Git Strategy

- **The user runs all Git commands that change state.** Read-only commands (e.g. `git status`, `git diff`, `git log`, `git show`) are allowed. Never run commands that modify the repository or remote (e.g. `add`, `commit`, `push`, `branch`, `merge`, `rebase`, `reset`, `stash`), directly or indirectly, and never use GitHub tools, the `gh` CLI, or APIs to branch, commit, push, open, or merge PRs. Provide exact commands, explain them, and wait for output when needed.
- One focused branch and PR per coherent change, targeting `main`. Use **Conventional Commits** (`type(scope): description`) for commits and PR titles, and **squash and merge**. Provide only the PR title: Greptile writes PR descriptions, and the user links issues in the PR sidebar so they close on merge.
- **Never add `Co-authored-by:` or any co-author attribution** to commits, squash messages, PR descriptions, or suggested commands.
- Keep issues concise: at most three bullet points covering scope and acceptance criteria.
