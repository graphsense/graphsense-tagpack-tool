#!/bin/sh

# apply custom settings
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /tmp/postgres-conf.sql

# create user
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" << EOF
CREATE USER $POSTGRES_USER_TAGSTORE WITH PASSWORD '$POSTGRES_PASSWORD_TAGSTORE';
CREATE USER read_user WITH PASSWORD '$POSTGRES_PASSWORD_TAGSTORE_READONLY';
-- setup fuzzy search resources
DROP EXTENSION IF EXISTS fuzzystrmatch;
DROP EXTENSION IF EXISTS pg_trgm;

CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
EOF

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

-- grant read-only access to do at least basic tag inserts
CREATE ROLE userinsertedtags;
GRANT INSERT ON TABLE public.tag TO userinsertedtags;
GRANT INSERT ON TABLE public.tagpack TO userinsertedtags;
GRANT INSERT ON TABLE public.tag_concept TO userinsertedtags;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO userinsertedtags;
GRANT userinsertedtags TO read_user;

ALTER SCHEMA public OWNER TO "$POSTGRES_USER_TAGSTORE";

EOF
