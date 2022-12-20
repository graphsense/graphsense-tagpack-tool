![Test TagPack Tool](https://github.com/graphsense/graphsense-tagpack-tool/actions/workflows/test_and_build.yaml/badge.svg)

# GraphSense TagPack Management Tool

This repository provides a command line tool for managing [GraphSense TagPacks](https://github.com/graphsense/graphsense-tagpacks/wiki/GraphSense-TagPacks). It can be used for

1. [validating TagPacks against the TagPack schema](#validation)
2. [validating ActorPacks against the ActorPack schema](#actorpack_validation)
3. [handling taxonomies and concepts](#taxonomies)
4. [ingesting TagPacks and related data into a TagStore](#tagstore)
5. [calculating the quality of the tags in the TagStore](#quality)

Please note that the last feature requires (installation of) a [Postgresql](https://www.postgresql.org/) database.

## Installation

    pip install git+https://github.com/graphsense/graphsense-tagpack-tool.git

## Validate a TagPack <a name="validation"></a>

Validate a single TagPack file

    tagpack-tool tagpack validate tests/testfiles/simple/ex_addr_tagpack.yaml

Recursively validate all TagPacks in (a) given folder(s).

    tagpack-tool tagpack validate tests/testfiles/

Tagpacks are validated against the [tagpack schema](src/tagpack/conf/tagpack_schema.yaml).

Confidence settings are validated against a set of acceptable [confidence](src/tagpack/db/confidence.csv) values.

## Validate an ActorPack <a name="actorpack_validation"></a>

Validate a single ActorPack file

    tagpack-tool actorpack validate tests/testfiles/actors/ex_actorpack.yaml

Recursively validate all TagPacks in (a) given folder(s).

    tagpack-tool actorpack validate tests/testfiles/actors/

Actorpacks are validated against the [actorpack schema](src/tagpack/conf/actorpack_schema.yaml).

Values in the field jurisdictions are validated against a set of [country codes](src/tagpack/db/countries.csv).

## View available taxonomies and concepts <a name="taxonomies"></a>

List configured taxonomy keys and URIs

    tagpack-tool taxonomy list

Fetch and show concepts of a specific remote/local taxonomy (referenced by key: abuse, entity, confidence, country)

    tagpack-tool taxonomy show entity

## Ingest TagPacks and related data into a TagStore <a name="tagstore"></a>

### Prerequisites: TagStore - PostgreSQL database

#### Option 1: Start a dockerized PostgreSQL database

- [Docker][docker], see e.g. https://docs.docker.com/engine/install/
- Docker Compose: https://docs.docker.com/compose/install/

Setup and start a PostgreSQL instance. First, copy `docker/env.template`
to `.env` and fill the fields `POSTGRES_PASSWORD` and `POSTGRES_PASSWORD_TAGSTORE`.

Start a PostgreSQL instance using Docker Compose:

    docker-compose up -d

This will automatically create the database schema as defined
in `src/tagpack/db/tagstore_schema.sql`.

#### Option 2: Use an existing PostgreSQL database

Create the schema and tables in a PostgreSQL instance of your choice

    psql -h $POSTGRES_HOST -d $POSTGRES_DB -U $POSTGRES_USER --password -f src/tagpack/db/tagstore_schema.sql

### Export .env variables

tagpack-tool is able to use the variables configured in the `.env` file to avoid specifying the parameter `--url` each time it connects to the database. The `--url` parameter will override the environment values if needed. To export the environment variables in `.env` from a linux shell (e.g. bash), first use:

    source .env
    export $(grep --regexp ^[A-Z] .env | cut -d= -f1)

Or just export each variable using:

    export POSTGRES_USER=VALUE
    export POSTGRES_PASSWORD=VALUE
    export POSTGRES_HOST=VALUE
    export POSTGRES_DB=VALUE

Then call tagpack-tool.

### Create and display a configuration file that defines which taxonomies to use

To create a default configuration `config.yaml` file from scratch - i.e. when config.yaml does not exist - use:

    tagpack-tool config

If a config.yaml already exists, it will not be replaced.

Show the contents of the config file:

    tagpack-tool config -v

To use a specific config file pass the file's location:

    tagpack-tool --config  path/to/config.yaml config

### Initialize the tagstore database

To initialize the database with all the taxonomies needed for ingesting the tagpacks, use:

    tagpack-tool tagstore init

### Ingest taxonomies and confidence scores

To insert individual taxonomies into database, use:

    tagpack-tool taxonomy insert abuse
    tagpack-tool taxonomy insert entity
    tagpack-tool taxonomy insert confidence
    tagpack-tool taxonomy insert country

To insert all configured taxonomies at once, simply omit taxonomy name

    tagpack-tool taxonomy insert

### Ingest TagPacks

Insert a single TagPack file or all TagPacks from a given folder

    tagpack-tool tagpack insert tests/testfiles/simple/ex_addr_tagpack.yaml
    tagpack-tool tagpack insert tests/testfiles/simple/multiple_tags_for_address.yaml
    tagpack-tool tagpack insert tests/testfiles/

By default, TagPacks are declared as non-public in the database.
For public TagPacks, add the `--public` flag to your arguments:

    tagpack-tool tagpack insert --public tests/testfiles/

If you try to insert tagpacks that already exist in the database, the ingestion process will be stopped.

To force **re-insertion** (if tagpack file contents have been modified), add the `--force` flag to your arguments:

    tagpack-tool tagpack insert --force tests/testfiles/

To ingest **new** tagpacks and **skip** over already ingested tagpacks, add the `--add_new` flag to  your arguments:

    tagpack-tool tagpack insert --add_new tests/testfiles/

By default, trying to insert tagpacks from a repository with **local** modifications will **fail**.
To force insertion despite local modifications, add the ``--no_strict_check`` command-line parameter

    tagpack-tool tagpack insert --no_strict_check tests/testfiles/

By default, tagpacks in the TagStore provide a backlink to the original tagpack file in their remote git repository.
To write local file paths instead, add the ``--no_git`` command-line parameter

    tagpack-tool tagpack insert --no_git --add_new tests/testfiles/

### Ingest ActorPacks

Insert a single ActorPack file or all ActorPacks from a given folder:

    tagpack-tool actorpack insert tests/testfiles/simple/ex_addr_actorpack.yaml
    tagpack-tool actorpack insert tests/testfiles/

You can use the parameters `--force`, `--add_new`, `--no_strict_check` and `--no_git` options in the same way as with the `tagpack` command.

### Align ingested attribution tags with GraphSense cluster Ids

The final step after inserting a tagpack is to fetch the corresponding
Graphsense cluster mapping ids for the crypto addresses in the tagpack.

Copy `src/tagpack/conf/ks_map.json.template` to `ks_map.json` and edit the file to
suit your Graphsense setup.

Then fetch the cluster mappings from your Graphsense instance and insert them
into the tagstore database:

    tagpack-tool tagstore insert_cluster_mappings -d $CASSANDRA_HOST -f ks_map.json

To update ALL cluster-mappings in your tagstore, add the `--update` flag:

    tagpack-tool tagstore insert_cluster_mappings --update -d $CASSANDRA_HOST -f ks_map.json

### Remove duplicate tags

Different tagpacks may contain identical tags - the same label and source for a particular address.
To remove such redundant information, run

    tagpack-tool tagstore remove_duplicates

### IMPORTANT: Keeping data consistency after tagpack insertion

After all required tagpacks have been ingested, run

    tagpack-tool tagstore refresh_views

to update all materialized views.
Depending on the amount of tags contained in the tagstore, this may take a while.

### Connection Pooling for PostgreSQL

For setups which expect many parallel connections to the tagstore it can be a good option to run all connections over a dedicated connection-pooler (to avoid exhausting the connections). The docker-compose file used to start the postgres instance automatically starts a pg-bounce container as well. The pg-bounce instance runs on port 6432 and can be used as a drop in replacement for the standard pgsql connections over port 5432. To use pg-bounce as connection-pooler configure the additional environment variables

    POSTGRES_USER_TAGSTORE=<user that is used to connect to the tagstore>
    POSTGRES_PASSWORD_TAGSTORE=<PASSWORD>

for example in the your local .env file. Currently, the pg-bounce setup only allows connections with this specific user configured in POSTGRES_USER_TAGSTORE.

## Calculate the quality of the tags in the TagStore <a name="quality"></a>

To assess on the quality of address tags we define a quality measure. For an address, it is calculated as the weighted similarity distance between all pairs of distinct tags assigned to the same address. For instance, an address with a unique tag has a quality equal to 1, while an address with several similar tags has a quality close to 0.

To calculate the quality measure for all the tags in the database, run:

    tagpack-tool quality calculate

To show the quality measures of all the tags in the database, or those of a specific crypto-currency, run:

    tagpack-tool quality show [--currency [BCH|BTC|ETH|LTC|ZEC]]

## Show tagstore contents/contributions

To list all tagpack creators and their contributions to a tagstore's content use:

    tagpack-tool tagstore show_composition

## Working in development / testing mode

    git clone https://github.com/graphsense/graphsense-tagpack-tool.git
    cd graphsense-tagpack-tool

### Using Pip locally

Create and activate a python environment for required dependencies and activate it

#### Venv

    python3 -m venv venv
    source venv/bin/activate

#### Conda

    conda create -n tagpack-tool
    conda activate tagpack-tool


Install package and dependencies in local environment

    make install-dev

### Linting and Formatting

The code in this repos will be autoformated via black and linted via a pre-commit hook. To manually format and lint the code run:

    make format && make pre-commit

Or linting via tox

    tox -l lint

### Build for Publishing

    make build

### Create Html Docs

    make docs

### Testing

Run tests

    make test

Or via tox

    tox

Check test coverage (optional)

    make test
    coverage report

Use [act][act] to check if test via [Github action](https://github.com/features/actions) pass.

[act]: https://github.com/nektos/act
[docker]: https://www.docker.com
[graphsense-transformation]: https://github.com/graphsense/graphsense-transformation
