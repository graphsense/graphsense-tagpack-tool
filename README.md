![Test TagPack Tool](https://github.com/graphsense/graphsense-tagpack-tool/workflows/Test%20TagPack%20Tool/badge.svg)

# GraphSense TagPack Management Tool



This repository defines a common structure (schema) for TagPacks and provides a tool for  
* ingesting taxonomies and concepts
* validating TagPacks 
* ingesting TagPacks into a PostgreSQL database.
* ingesting GraphSense cluster mappings  


## Prerequisites: PostgreSQL database

### Option 1: dockerised database

- [Docker][docker], see e.g. https://docs.docker.com/engine/install/
- Docker Compose: https://docs.docker.com/compose/install/

Setup and start a PostgreSQL instance. First, copy `tagpack/conf/env.template` to `.env`
and fill in all parameters:

`LOCAL_DATA_DIR`, the persisted PostgreSQL data directory on the local machine,
and all PostgreSQL connection parameters
- `POSTGRES_HOST`
- `POSTGRES_USER`
- `POSTGRES_DB`
- `POSTGRES_PASSWORD`

Start an PostgreSQL instance using Docker Compose:

    docker-compose up -d

This will automatically create the database schema as defined
in `scripts/tagstore_schema.sql`.

### Option 2: create the schema and tables in a PostgreSQL instance of your choice    

    psql -h $DBHOST -p $DBPORT -d $DB -U $DBUSER --password -f tagpack/db/tagstore_schema.sql


## Install tagpack-tools

Create and activate a python environment for required dependencies

    python3 -m venv venv
    source venv/bin/activate
    python -m pip install -U pip wheel setuptools

Install package and dependencies in local environment

    pip install .

## Handling Taxonomies

Create a default config.yaml (interactively)

    tagpack-tool config

List configured taxonomy keys and URIs

    tagpack-tool taxonomy

Fetch and show concepts of a specific remote taxonomy (referenced by key)

    tagpack-tool taxonomy show entity

Insert concepts from a remote taxonomy into database

    tagpack-tool taxonomy insert abuse -u postgresql://$USER:$PASSWORD@$DBHOST:$DBPORT/tagstore


## Validate a TagPack

Validate a single TagPack file

    tagpack-tool validate tests/testfiles/ex_addr_tagpack.yaml
    tagpack-tool validate tests/testfiles/ex_entity_tagpack.yaml

Recursively validate all TagPacks in (a) given folder(s).

    tagpack-tool validate tests/testfiles/

## Insert a TagPack into database

Insert a single TagPack file or all TagPacks from a given folder

    tagpack-tool insert tests/testfiles/ex_addr_tagpack.yaml
    tagpack-tool insert tests/testfiles/ex_entity_tagpack.yaml
    tagpack-tool insert tests/testfiles/

Create a keyspace and insert all TagPacks from a given folder

    tagpack-tool insert -s -k tagpacks tests/testfiles/

Optionally, you can specify the level of `concurrency` (default: 100) by using
the `-c` parameter.

    tagpack-tool insert -c 500 -s -k tagpacks tests/testfiles

## Insert GraphSense cluster mappings into database

Copy `tagpack/conf/ks_map.json.template` to `ks_map.json` and edit the file to suit your setup.

Then copy the required cluster mappings 
    
    tagpack-tool cluster -d $CASSANDRA_HOST -k ks_map.json -u  postgresql://$USER:$PASSWORD@$DBHOST:$DBPORT/tagstore



## Development / Testing

Install packages via `requirements.txt`

    pip install -r requirements.txt

Run tests

    pytest

Check test coverage (optional)
    
    pip install coverage

    coverage run -m pytest
    coverage report

Use [act][act] to check if test via [Github action](https://github.com/features/actions) pass.

[act]: https://github.com/nektos/act
[docker]: https://www.docker.com
[graphsense-transformation]: https://github.com/graphsense/graphsense-transformation
