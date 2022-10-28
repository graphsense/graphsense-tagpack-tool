![Test TagPack Tool](https://github.com/graphsense/graphsense-tagpack-tool/workflows/Test%20TagPack%20Tool/badge.svg)

# GraphSense TagPack Management Tool

This repository provides a command line tool for managing [GraphSense TagPacks](https://github.com/graphsense/graphsense-tagpacks/wiki/GraphSense-TagPacks). It can be used for 

1. [validating TagPacks against the TagPack schema](#validation)
2. [handling taxonomies and concepts](#taxonomies)
3. [ingesting TagPacks and related data into a TagStore](#tagstore)
4. [calculating the quality of the tags in the TagStore](#quality)

Please note that the last feature requires (installation of) a [Postgresql](https://www.postgresql.org/) database.

## Installation

    pip install git+https://github.com/graphsense/graphsense-tagpack-tool.git

## Validate a TagPack <a name="validation"></a>

Validate a single TagPack file

    tagpack-tool validate tests/testfiles/ex_addr_tagpack.yaml
    tagpack-tool validate tests/testfiles/ex_entity_tagpack.yaml

Recursively validate all TagPacks in (a) given folder(s).

    tagpack-tool validate tests/testfiles/

Tagpacks are validated against the [tagpack schema](tagpack/conf/tagpack_schema.yaml).

Confidence settings are validated against a set of acceptable [confidence](tagpack/conf/confidence.csv) values.

## View available taxonomies and concepts <a name="taxonomies"></a>

List configured taxonomy keys and URIs

    tagpack-tool taxonomy

Fetch and show concepts of a specific remote taxonomy (referenced by key)

    tagpack-tool taxonomy show entity

## Ingest TagPacks and related data into a TagStore <a name="tagstore"></a>

### Prerequisites: TagStore - PostgreSQL database

#### Option 1: Start a dockerized PostgreSQL database

- [Docker][docker], see e.g. https://docs.docker.com/engine/install/
- Docker Compose: https://docs.docker.com/compose/install/

Setup and start a PostgreSQL instance. First, copy `docker/env.template`
to `.env` and fill the fields `POSTGRES_PASSWORD` and `POSTGRES_PASSWORD_TAGSTORE`.

Start an PostgreSQL instance using Docker Compose:

    docker-compose up -d

This will automatically create the database schema as defined
in `scripts/tagstore_schema.sql`.

#### Option 2: Use an existing PostgreSQL database

Create the schema and tables in a PostgreSQL instance of your choice    

    psql -h $DBHOST -p $DBPORT -d $DB -U $DBUSER --password -f tagpack/db/tagstore_schema.sql

### Ingest confidence scores

    psql \
        -h $DBHOST \
        -p $DBPORT \
        -d $DB \
        -U $DBUSER \
        --password \
        -c "\copy tagstore.confidence(id,label,description,level) from 'tagpack/db/confidence.csv' delimiter ',' csv header;"

### Export .env variables

tagpack-tool is able to use the variables configured in the `.env` file to avoid specifying the parameter `--url` each time it connects to the database. The `--url` parameter will override the environment values if needed. To export the environment variables in `.env` from a linux shell (e.g. bash), first use:

    source .env
    export $(grep --regexp ^[A-Z] .env | cut -d= -f1)

Then call tagpack-tool.

### Ingest taxonomies

Insert concepts from a remote taxonomy into database, e.g. abuse:

    tagpack-tool taxonomy insert abuse -u postgresql://$USER:$PASSWORD@$DBHOST:$DBPORT/tagstore
    tagpack-tool taxonomy insert entity -u postgresql://$USER:$PASSWORD@$DBHOST:$DBPORT/tagstore

resp. to insert all configured taxonomies at once, simply omit taxonomy name

    tagpack-tool taxonomy insert -u postgresql://$USER:$PASSWORD@$DBHOST:$DBPORT/tagstore

### Ingest TagPacks

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

### Align ingested attribution tags with GraphSense cluster Ids

The final step after inserting a tagpack is to fetch the corresponding
Graphsense cluster mapping ids for the crypto addresses in the tagpack.

Copy `tagpack/conf/ks_map.json.template` to `ks_map.json` and edit the file to
suit your Graphsense setup.

Then fetch the cluster mappings from your Graphsense instance and insert them
into the tagstore database:  
    
    tagpack-tool cluster -d $CASSANDRA_HOST -f ks_map.json -u postgresql://$USER:$PASSWORD@$DBHOST:$DBPORT/tagstore

To update ALL cluster-mappings in your tagstore, add the `--update` flag:

    tagpack-tool cluster --update -d $CASSANDRA_HOST -f ks_map.json -u postgresql://$USER:$PASSWORD@$DBHOST:$DBPORT/tagstore

### Remove duplicate tags

Different tagpacks may contain identical tags - the same label and source for a particular address. 
To remove such redundant information, run

    tagpack db remove_duplicates

### IMPORTANT: Keeping data consistency after tagpack insertion

After all required tagpacks have been ingested, run

    tagpack-tool db refresh_views

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

    tagpack-tool quality calculate -u postgresql://$USER:$PASSWORD@$DBHOST:$DBPORT/tagstore

To show the quality measures of all the tags in the database, or those of a specific crypto-currency, run:

    tagpack-tool quality show -u postgresql://$USER:$PASSWORD@$DBHOST:$DBPORT/tagstore [--currency [BCH|BTC|ETH|LTC|ZEC]]

## Working in development / testing mode

    git clone https://github.com/graphsense/graphsense-tagpack-tool.git
    cd graphsense-tagpack-tool

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

Once the *conda environment is active*, install giturlparse and this tagpack-tool package using pip:

    pip install giturlparse coinaddrvalidator
    pip install .

### Testing

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
