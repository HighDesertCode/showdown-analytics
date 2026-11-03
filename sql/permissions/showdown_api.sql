-- Grants for the public API's user. It reads the api schema and nothing else: no reference, raw, or staging, and
-- no future private schemas. The api reference views still work, because a view reads its tables with its owner's
-- (dbt's) privileges.

-- showdown_analyst.sql revokes the defaults from PUBLIC; see it for why the database isn't named.
DO $$
BEGIN
    EXECUTE FORMAT('GRANT CONNECT ON DATABASE %I TO "showdown-api"', CURRENT_DATABASE());
END
$$;

GRANT USAGE ON SCHEMA api TO "showdown-api";
GRANT SELECT ON ALL TABLES IN SCHEMA api TO "showdown-api";
-- dbt recreates the api tables on every build, which drops grants made on the old ones, so grant on the tables and
-- views showdown-transform creates from now on.
ALTER DEFAULT PRIVILEGES FOR ROLE "showdown-transform" IN SCHEMA api
    GRANT SELECT ON TABLES TO "showdown-api";

-- The API is public, so cap what it can hold: a few pooled connections, and no query longer than five seconds.
ALTER ROLE "showdown-api" CONNECTION LIMIT 10;
ALTER ROLE "showdown-api" SET statement_timeout = '5s';
