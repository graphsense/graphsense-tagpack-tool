![Test TagPack Tool](https://github.com/graphsense/graphsense-tagpack-tool/workflows/Test%20TagPack%20Tool/badge.svg)

# TagPack Management Tool

This repository defines a common structure (schema) for TagPacks and provides a
tool for  

* validating TagPacks
* handling taxonomies and concepts
* ingesting TagPacks into a PostgreSQL database, a so-called TagStore
* ingesting GraphSense cluster mappings  

A TagPack is a collection of attribution tags, which associate cryptoasset addresses or GraphSense entities with real-world actors such as exchanges. 

To learn more about TagPacks, continue [reading here](README_tagpacks.md).

## Prerequisites: TagStore - PostgreSQL database

### Option 1: dockerized database

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


## Installation

### Using Pip

    pip install git+https://github.com/graphsense/graphsense-tagpack-tool.git

### Using Pip locally

Create and activate a python environment for required dependencies

    python3 -m venv venv
    source venv/bin/activate
    python -m pip install -U pip wheel setuptools

Install package and dependencies in local environment

    pip install .

### Using Conda

Create and activate the conda environment

    conda env create -f environment.yml
    conda activate tagpack-tool

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

### Validation resources

Tagpacks are validated against the [tagpack schema](tagpack/conf/tagpack_schema.yaml).

Confidence settings are validated against a set of acceptable [confidence](tagpack/conf/confidence.csv)  values.

## Insert a TagPack into TagStore database

Insert a single TagPack file or all TagPacks from a given folder

    tagpack-tool insert tests/testfiles/ex_addr_tagpack.yaml
    tagpack-tool insert tests/testfiles/ex_entity_tagpack.yaml
    tagpack-tool insert tests/testfiles/

By default, TagPacks are declared as non-public in the database.
For public TagPacks, add the `--public` flag to your arguments:

    tagpack-tool insert --public tests/testfiles/

If you try to insert tagpacks that already exist in the database, the ingestion process will be stopped.

To force **re-insertion** (if tagpack file contents have been modified), add the `--force` flag to your arguments:

    tagpack-tool insert --force tests/testfiles/

To ingest **new** tagpacks and **skip** over already ingested tagpacks, add the `--add_new` flag to  your arguments:

    tagpack-tool insert --add_new tests/testfiles/


By default, trying to insert tagpacks from a repository with **local** modifications will **fail**.
To force insertion despite local modifications, add the ``--no_strict_check`` command-line parameter

    tagpack-tool insert --force --add_new tests/testfiles/

By default, tagpacks in the TagStore provide a backlink to the original tagpack file in their remote git repository ([see here](README_tagpacks.md#versioning-with-git)).
To instead write local file paths instead, add the ``--no_git`` command-line parameter

    tagpack-tool insert --no_git --add_new tests/testfiles/

## Insert GraphSense cluster mappings into database

The final step after inserting a tagpack is to fetch the corresponding
Graphsense cluster mapping ids for the crypto addresses in the tagpack.

Copy `tagpack/conf/ks_map.json.template` to `ks_map.json` and edit the file to
suit your Graphsense setup.

Then fetch the cluster mappings from your Graphsense instance and insert them
into the tagstore database:  
    
    tagpack-tool cluster -d $CASSANDRA_HOST -f ks_map.json -u postgresql://$USER:$PASSWORD@$DBHOST:$DBPORT/tagstore

To update ALL cluster-mappings in your tagstore, add the `--update` flag:

    tagpack-tool cluster --update -d $CASSANDRA_HOST -f ks_map.json -u postgresql://$USER:$PASSWORD@$DBHOST:$DBPORT/tagstore


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
