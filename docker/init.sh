#!/bin/sh

# apply custom settings
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /tmp/postgres-conf.sql

# create schema
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /tmp/schema.sql
# create user
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE USER $POSTGRES_USER_TAGSTORE WITH PASSWORD '$POSTGRES_PASSWORD_TAGSTORE';"
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE USER read_user WITH PASSWORD '$POSTGRES_PASSWORD_TAGSTORE_READONLY';"
# set permissions
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" << EOF
REVOKE CONNECT ON DATABASE "$POSTGRES_DB" FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;

GRANT ALL PRIVILEGES ON DATABASE "$POSTGRES_DB" TO "$POSTGRES_USER_TAGSTORE";
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO "$POSTGRES_USER_TAGSTORE";
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO "$POSTGRES_USER_TAGSTORE";

-- read-only access
CREATE ROLE readaccess;
GRANT CONNECT ON DATABASE "$POSTGRES_DB" TO readaccess;
GRANT USAGE ON SCHEMA public TO readaccess;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO readaccess;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO readaccess;
GRANT readaccess TO read_user;

ALTER SCHEMA public OWNER TO "$POSTGRES_USER_TAGSTORE";
ALTER MATERIALIZED VIEW public.label OWNER TO "$POSTGRES_USER_TAGSTORE";
ALTER MATERIALIZED VIEW public.statistics OWNER TO "$POSTGRES_USER_TAGSTORE";
ALTER MATERIALIZED VIEW public.tag_count_by_cluster OWNER TO "$POSTGRES_USER_TAGSTORE";
ALTER MATERIALIZED VIEW public.cluster_defining_tags_by_frequency_and_maxconfidence OWNER TO "$POSTGRES_USER_TAGSTORE";
EOF
