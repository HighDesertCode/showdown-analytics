# Project Overview

Showdown Analytics collects and analyzes competitive Pokémon data from Smogon and Pokémon Showdown, starting with Gen 9 Monotype. It stores monthly statistics, reference data, public replays, and private research in PostgreSQL, and will expose source-attributed analytics through a public API and website (including for ChatGPT).

See `REPORT.md` for research context and data interpretation. Always preserve source provenance, reporting periods, weighting baselines, team-type scopes, and metric denominators. Keep public replay samples distinct from ladder-wide statistics, and unknown battle information distinct from inferred facts.

# Infrastructure

All services run on DigitalOcean. Notion is used separately for personal notes. This is the intended architecture; only what `docs/database-architecture.md` lists as deployed actually exists. Stay within the current milestone (M1: database foundation).

- **Database:** Managed PostgreSQL. Project data goes in `showdown-database` via `showdown-analyst`; never use `defaultdb` or infer the database/user from cluster defaults. Schema changes go through SQL migrations run by a separate DDL-privileged account.
- **Developer access:** Tailscale subnet router on a Droplet in the database VPC, plus trusted sources and TLS with certificate verification.
- **Planned:** Spaces (raw archives), Python collectors run locally then on App Platform (with scheduling), a read-only FastAPI service, a Streamlit site and a public CLI that both consume only that API, and private research storage that is never reachable from public endpoints.

**Terraform:** Create services manually, write matching configuration, `terraform import`, and confirm a no-change plan before managing changes through Terraform. Keep state outside Git; never commit state, plans, credentials, or secret variable files.

**Security:** Least-privilege roles, private networking, and verified TLS. Never commit or log secrets; use environment variables and placeholder-only example files.

# Development

- **Layout:** One top-level directory per product: `pipelines/` (internal data loading; the only code that writes to the database), and later `api/`, `web/`, and `cli/` (the public CLI, which uses only the API). Tests mirror it under `tests/<product>/`.
- **SQL:** `sql/create/`, `sql/index/`, and `sql/permissions/` hold one file per table or role, run manually as `doadmin` in foreign-key order. No migration tooling yet.
- **Reference data:** Showdown's own data files are the source of truth (not PokeAPI). Loaders insert only new rows, skipping existing `showdown_id`s up front rather than using `ON CONFLICT`, and run in one transaction.
- **Running pipelines:** `uv run --env-file .env pipelines <command>`; `.env` holds libpq `PG*` variables with `PGSSLMODE=verify-full`.
- **Tooling:** pytest, Ruff (120-character lines; rules `E`, `F`, `I`, `UP`, `B`), and ty (beta, pinned to an exact version). Before committing:

  ```bash
  uv run ruff check --fix pipelines tests/pipelines   # fixes lint issues, including sorting imports
  uv run ruff format pipelines tests/pipelines        # formats the code
  uv run ty check pipelines tests/pipelines           # type checks
  uv run pytest tests/pipelines                       # runs tests
  ```

- **CI:** One workflow per product and check, named `python-<product>-<check>.yml` (`tests`, `lint`, `type-checker`), each triggered only by changes to that product's paths.
- **Deferred:** dbt is reconsidered in M2 when derived statistics views begin.

# Git Strategy

- **The user runs all Git commands that change state.** Read-only commands (e.g. `git status`, `git diff`, `git log`, `git show`) are allowed. Never run commands that modify the repository or remote (e.g. `add`, `commit`, `push`, `branch`, `merge`, `rebase`, `reset`, `stash`), directly or indirectly, and never use GitHub tools, the `gh` CLI, or APIs to branch, commit, push, open, or merge PRs. Provide exact commands, explain them, and wait for output when needed.
- One focused branch and PR per coherent change, targeting `main`. Use **Conventional Commits** (`type(scope): description`) for commits and PR titles, and **squash and merge**. Write PR descriptions that work as the squash commit body: change summary, issue references, validation, and limitations.
- **Never add `Co-authored-by:` or any co-author attribution** to commits, squash messages, PR descriptions, or suggested commands.
- Keep issues concise: at most three bullet points covering scope and acceptance criteria.
