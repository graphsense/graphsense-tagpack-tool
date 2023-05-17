#!/bin/sh

# apply custom settings
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /tmp/conf.sql

# create schema
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /tmp/schema.sql
# create user
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE USER $POSTGRES_USER_TAGSTORE WITH PASSWORD '$POSTGRES_PASSWORD_TAGSTORE';"
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE USER read_user WITH PASSWORD '$POSTGRES_PASSWORD_TAGSTORE_READONLY';"
# set permissions
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" << EOF
REVOKE CONNECT ON DATABASE "$POSTGRES_DB" FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA tagstore FROM PUBLIC;

GRANT ALL PRIVILEGES ON DATABASE "$POSTGRES_DB" TO "$POSTGRES_USER_TAGSTORE";
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA tagstore TO "$POSTGRES_USER_TAGSTORE";
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA tagstore TO "$POSTGRES_USER_TAGSTORE";

-- read-only access
CREATE ROLE readaccess;
GRANT CONNECT ON DATABASE "$POSTGRES_DB" TO readaccess;
GRANT USAGE ON SCHEMA tagstore TO readaccess;
GRANT SELECT ON ALL TABLES IN SCHEMA tagstore TO readaccess;
ALTER DEFAULT PRIVILEGES IN SCHEMA tagstore GRANT SELECT ON TABLES TO readaccess;
GRANT readaccess TO read_user;

ALTER SCHEMA tagstore OWNER TO "$POSTGRES_USER_TAGSTORE";
ALTER MATERIALIZED VIEW tagstore.label OWNER TO "$POSTGRES_USER_TAGSTORE";
ALTER MATERIALIZED VIEW tagstore.statistics OWNER TO "$POSTGRES_USER_TAGSTORE";
ALTER MATERIALIZED VIEW tagstore.tag_count_by_cluster OWNER TO "$POSTGRES_USER_TAGSTORE";
ALTER MATERIALIZED VIEW tagstore.cluster_defining_tags_by_frequency_and_maxconfidence OWNER TO "$POSTGRES_USER_TAGSTORE";
EOF
