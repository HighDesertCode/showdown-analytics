-- Grants for the project's loader user. Loaders are insert-only, so no UPDATE or DELETE.
-- Default privileges apply to tables doadmin creates later; ON ALL TABLES covers existing ones.

GRANT USAGE ON SCHEMA reference TO "showdown-analyst";
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA reference TO "showdown-analyst";
ALTER DEFAULT PRIVILEGES FOR ROLE doadmin IN SCHEMA reference
    GRANT SELECT, INSERT ON TABLES TO "showdown-analyst";

-- Every role can connect to every database by default; keep project roles out of defaultdb.
REVOKE CONNECT ON DATABASE defaultdb FROM PUBLIC;
