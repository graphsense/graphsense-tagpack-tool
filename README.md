![Test TagPack Tool](https://github.com/graphsense/graphsense-tagpack-tool/workflows/Test%20TagPack%20Tool/badge.svg)

# GraphSense TagPack Management Tool

This repository defines a common structure (schema) for TagPacks and provides a
tool for validating and ingesting TagPacks into [Apache Cassandra][cassandra].

The TagPack management tool supports validation of TagPacks and ingestion into
an [Apache Cassandra database][cassandra], which is required before running
the [GraphSense transformation][graphsense-transformation] pipeline.
It is made available as a Python package.

## Local Installation

Create and activate a python environment for required dependencies

    python3 -m venv venv
    source venv/bin/activate
    python -m pip install -U pip wheel setuptools

Install package and dependencies in local environment

    pip install .

### Handling Taxonomies

List configured taxonomy keys and URIs

    tagpack-tool taxonomy

Fetch and show concepts of a specific remote taxonomy (referenced by key)

    tagpack-tool taxonomy show entity

Insert concepts from a remote taxonomy into Cassandra

    tagpack-tool taxonomy insert abuse

Use the `-s / --setup-keyspace` (and `-k`) option to (re-)create the keyspace

    tagpack-tool taxonomy insert -s -k tagpacks abuse

### Validate a TagPack

Validate a single TagPack file

    tagpack-tool validate tests/testfiles/ex_addr_tagpack.yaml
    tagpack-tool validate tests/testfiles/ex_entity_tagpack.yaml

Recursively validate all TagPacks in (a) given folder(s).

    tagpack-tool validate tests/testfiles/

### Insert a TagPack into Cassandra

Insert a single TagPack file or all TagPacks from a given folder

    tagpack-tool insert tests/testfiles/ex_addr_tagpack.yaml
    tagpack-tool insert tests/testfiles/ex_entity_tagpack.yaml
    tagpack-tool insert tests/testfiles/

Create a keyspace and insert all TagPacks from a given folder

    tagpack-tool insert -s -k tagpacks tests/testfiles/

Optionally, you can specify the level of `concurrency` (default: 100) by using
the `-c` parameter.

    tagpack-tool insert -c 500 -s -k tagpacks tests/testfiles

## Development / Testing

Speed-up building of [cassandra-driver](https://docs.datastax.com/en/developer/python-driver/3.25/installation/) from source.

    CASS_DRIVER_BUILD_CONCURRENCY=8

Use the `-e` option for linking package to sources (for development purposes)

    pip install -e .

OR install packages via `requirements.txt`

    pip install -r requirements.txt

Run tests

    pytest

Check test coverage (optional)
    
    pip install coverage

    coverage run -m pytest
    coverage report

Use [act][act] to check if test via [Github action](https://github.com/features/actions) pass.

[act]: https://github.com/nektos/act
[cassandra]: https://cassandra.apache.org
[graphsense-transformation]: https://github.com/graphsense/graphsense-transformation
