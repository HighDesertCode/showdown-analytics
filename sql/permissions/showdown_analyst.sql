-- Grants for the project's loader user. Loaders are insert-only (no DELETE, and UPDATE only on run tracking).
-- Default privileges apply to tables doadmin creates later; ON ALL TABLES covers existing ones.

GRANT USAGE ON SCHEMA reference TO "showdown-analyst";
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA reference TO "showdown-analyst";
ALTER DEFAULT PRIVILEGES FOR ROLE doadmin IN SCHEMA reference
    GRANT SELECT, INSERT ON TABLES TO "showdown-analyst";

GRANT USAGE ON SCHEMA raw TO "showdown-analyst";
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA raw TO "showdown-analyst";
ALTER DEFAULT PRIVILEGES FOR ROLE doadmin IN SCHEMA raw
    GRANT SELECT, INSERT ON TABLES TO "showdown-analyst";

-- The one exception to insert-only: a run updates its own progress and result. Smogon data stays immutable.
GRANT UPDATE (finished_at, status, files_loaded, files_skipped, files_failed, error)
    ON raw.ingestion_run TO "showdown-analyst";

-- Every role can connect to every database, and create temporary tables in it, by default. Keep project roles
-- out of defaultdb, and let only the project's roles into this one. Run while connected to showdown-database;
-- current_database() names it, since the tests run these files against a database with another name.
REVOKE CONNECT ON DATABASE defaultdb FROM PUBLIC;
DO $$
BEGIN
    EXECUTE FORMAT('REVOKE CONNECT, TEMPORARY ON DATABASE %I FROM PUBLIC', CURRENT_DATABASE());
    EXECUTE FORMAT('GRANT CONNECT ON DATABASE %I TO "showdown-analyst"', CURRENT_DATABASE());
END
$$;
