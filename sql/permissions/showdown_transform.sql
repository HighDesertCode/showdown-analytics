-- Grants for dbt (transform/). It reads source data and builds the staging and api schemas.
-- It owns the views and tables it creates there, so it can rebuild them; it cannot change source data.

-- showdown_analyst.sql revokes the defaults from PUBLIC; see it for why the database isn't named. dbt's unit
-- tests build their fixtures in temporary tables.
DO $$
BEGIN
    EXECUTE FORMAT('GRANT CONNECT, TEMPORARY ON DATABASE %I TO "showdown-transform"', CURRENT_DATABASE());
END
$$;

GRANT USAGE ON SCHEMA reference, raw TO "showdown-transform";
GRANT SELECT ON ALL TABLES IN SCHEMA reference, raw TO "showdown-transform";
ALTER DEFAULT PRIVILEGES FOR ROLE doadmin IN SCHEMA reference, raw
    GRANT SELECT ON TABLES TO "showdown-transform";

GRANT USAGE, CREATE ON SCHEMA staging, api TO "showdown-transform";
