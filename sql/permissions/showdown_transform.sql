-- Grants for dbt (transform/). It reads source data and builds the staging and api schemas.
-- It owns the views and tables it creates there, so it can rebuild them; it cannot change source data.

GRANT USAGE ON SCHEMA reference, raw TO "showdown-transform";
GRANT SELECT ON ALL TABLES IN SCHEMA reference, raw TO "showdown-transform";
ALTER DEFAULT PRIVILEGES FOR ROLE doadmin IN SCHEMA reference, raw
    GRANT SELECT ON TABLES TO "showdown-transform";

GRANT USAGE, CREATE ON SCHEMA staging, api TO "showdown-transform";
