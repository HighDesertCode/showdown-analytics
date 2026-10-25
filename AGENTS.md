# Project Overview

Showdown Analytics collects and analyzes competitive Pokémon data from Smogon and Pokémon Showdown, with an initial focus on Generation 9 Monotype. The project combines monthly statistics, Pokémon reference data, public battle replays, and private competitive research in PostgreSQL. A public API and website will make source-attributed analytics available to users and external clients, including ChatGPT.

Use `REPORT.md` for research context and data interpretation. Preserve source provenance, reporting periods, weighting baselines, team-type scopes, and metric denominators. Keep public replay samples distinct from ladder-wide statistics, and keep unknown battle information distinct from inferred facts.

# Infrastructure

DigitalOcean is the chosen cloud provider, and all project services will be deployed on DigitalOcean. Notion remains an external tool for personal notes and research.

Use Terraform to manage cloud infrastructure. Create services manually first, then write matching Terraform resource configuration and adopt the supported resources using `terraform import`. Validate the imported configuration with a plan showing no changes before making subsequent infrastructure changes through Terraform. Establish this workflow in M1 and extend it as later milestones introduce services. Keep database schema changes in SQL migrations. Store Terraform state securely outside Git, document state access and locking, and never commit state files, saved plans, credentials, or secret variable files.

The planned infrastructure is:

- **Database:** DigitalOcean Managed PostgreSQL, with version-controlled SQL migrations, appropriate constraints and indexes, and separate permissions for migrations, ingestion, public reads, and private research.
- **Developer database access:** A small DigitalOcean Droplet in the database VPC is the planned Tailscale subnet router. Approved tailnet clients reach the private database endpoint through restricted routes and access rules; database trusted sources and TLS verification provide additional controls. Create the Droplet manually before Terraform adoption.
- **Raw data archive:** DigitalOcean Spaces for original Smogon datasets and replay payloads, linked to their database records.
- **Data ingestion:** Portable Python collectors and parsers that run locally and can later execute in containers on DigitalOcean App Platform.
- **Scheduling:** DigitalOcean App Platform for scheduled collection, retries, recovery, and ingestion monitoring.
- **Public API:** A read-only FastAPI service backed by PostgreSQL, deployed on DigitalOcean App Platform.
- **Website:** A Streamlit application deployed on DigitalOcean App Platform. Initial local application configuration belongs to issue #2; analytics features and public deployment belong to later milestones.
- **Private research:** Restricted database storage for personal teams, battle history, and research, with Notion used for personal notes and strategic documentation. Private research must remain inaccessible through public API endpoints.

Treat this as the intended architecture, not confirmation that resources have been provisioned. Follow the current milestone's scope. M1 establishes the database foundation; later milestones cover ingestion, scheduling, replay collection, personal analytics, and the public platform.

Secure database access using private networking where available, restricted trusted sources, encrypted connections with certificate verification, and least-privilege roles. Provide a documented, secured connection path for local development. Never commit credentials or include secrets in logs or documentation; use environment variables and secret management, with placeholder-only example files.

# Git Strategy

- Keep issue titles and descriptions as concise as possible while preserving the scope and acceptance criteria needed to complete the work. Prefer to use bullet points and keep the number of bullet points to a maximum of three.
- **The user runs all Git-related commands.** Agents must never execute Git commands themselves, including read-only commands such as `git status`, `git diff`, `git log`, or `git remote`. Do not invoke Git indirectly through scripts, tools, subprocesses, or automation to bypass this rule.
- Provide the exact commands for the user to run whenever Git operations are needed. Explain their purpose and wait for the output when subsequent work depends on it.
- Do not perform Git workflow actions through GitHub tools, the GitHub CLI, or APIs as a workaround. This includes creating branches, committing, pushing, opening pull requests, or merging. Provide the commands for the user instead.
- Use a focused branch and pull request for each coherent change. Target `main`; do not commit directly to `main`.
- Use **Conventional Commits** for commit messages and pull request titles: `type(optional-scope): description`. Examples: `feat(database): add source tracking tables`, `fix(stats): preserve weighting denominators`, and `docs: document local database setup`.
- Use **squash and merge**. The pull request title becomes the Conventional Commit subject on `main`; prepare the PR description so it can serve as a clear squash commit body. The user should verify the final squash message before merging.
- Never add `Co-authored-by:` trailers or other co-author attribution to commit messages, including squash commit messages. Do not include such attribution in generated PR descriptions or suggested commands.
- Keep each pull request limited to its stated purpose. Include a concise explanation of the change, relevant issue references, validation performed, and material limitations.
