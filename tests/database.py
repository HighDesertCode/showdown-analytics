"""What a test database is built from: the SQL files in sql/, in the order they're run, and the project's roles.

tests/conftest.py builds the schemas from these for every product's tests, and tests/transform/setup_database.py for
the dbt build in CI. It's the same order used to run the files manually against showdown-database.
"""

from pathlib import Path

SQL_DIR = Path(__file__).resolve().parents[1] / "sql"
# Foreign-key order.
SQL_FILES = [
    "create/reference/schema.sql",
    "create/reference/type.sql",
    "create/reference/species.sql",
    "create/reference/ability.sql",
    "create/reference/species_ability.sql",
    "create/reference/move.sql",
    "create/reference/move_effect.sql",
    "create/reference/item.sql",
    "create/reference/nature.sql",
    "index/reference/species_ability.sql",
    "create/raw/schema.sql",
    "create/raw/source_file.sql",
    "create/raw/chaos_report.sql",
    "create/raw/chaos_pokemon.sql",
    "create/raw/chaos_option.sql",
    "create/raw/chaos_counter.sql",
    "create/raw/usage_report.sql",
    "create/raw/usage_pokemon.sql",
    "create/raw/leads_report.sql",
    "create/raw/leads_pokemon.sql",
    "create/raw/metagame_report.sql",
    "create/raw/metagame_tag.sql",
    "create/raw/matchup_chart_report.sql",
    "create/raw/matchup_chart_cell.sql",
    "create/raw/matchup_chart_viability.sql",
    "create/raw/ingestion_run.sql",
    "create/raw/replay.sql",
    "index/raw/replay.sql",
    "create/raw/replay_collection_run.sql",
    "create/raw/battle.sql",
    "create/raw/battle_side.sql",
    "create/raw/battle_pokemon.sql",
    "create/raw/battle_event.sql",
    "create/staging/schema.sql",
    "create/api/schema.sql",
]
PERMISSION_FILES = [
    "permissions/showdown_analyst.sql",
    "permissions/showdown_transform.sql",
    "permissions/showdown_api.sql",
]
ROLES = ["doadmin", "showdown-analyst", "showdown-transform", "showdown-api"]
PROTECTED_DATABASES = {"showdown-database", "defaultdb"}
