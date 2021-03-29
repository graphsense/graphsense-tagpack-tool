[![Build Status](https://travis-ci.org/graphsense/graphsense-tagpack-tool.svg?branch=master)](https://travis-ci.org/graphsense/graphsense-tagpack-tool)
[![Coverage Status](https://coveralls.io/repos/github/graphsense/graphsense-tagpack-tool/badge.svg?branch=master)](https://coveralls.io/github/graphsense/graphsense-tagpack-tool?branch=master)

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
    . venv/bin/activate

Install package and dependencies in local environment

    pip install .

### Handling Taxonomies

List configured taxonomy keys and URIs

    tagpack taxonomy

Fetch and show concepts of a specific remote taxonomy (referenced by key)

    tagpack taxonomy show entity

Insert concepts from a remote taxonomy into Cassandra

    tagpack taxonomy insert abuse

Use the `-s / --setup-keyspace` (and `-k`) option to (re-)create the keyspace

    tagpack taxonomy insert -s -k my_keyspace abuse

### Validate a TagPack

Validate a single TagPack file

    tagpack validate packs/demo.yaml

Recursively validate all TagPacks in (a) given folder(s).

    tagpack validate packs/

### Insert a TagPack into Cassandra

Insert a single TagPack file or all TagPacks from a given folder

    tagpack insert packs/demo.yaml
    tagpack insert packs/

Create a keyspace and insert all TagPacks from a given folder

    tagpack insert -s -k dummy_keyspace packs/

Optionally, you can specify the level of `concurrency` (default: 100) by using
the `-c` parameter.

    tagpack insert -c 500 -s -k dummy_keyspace packs/
    
## Development / Testing

Use the `-e` option for linking package to sources (for development purposes)

    pip install -e .

OR install packages via `requirements.txt`

    pip install -r requirements.txt

Run tests

    pytest

Check test coverage

    coverage run -m pytest
    coverage report

[cassandra]: https://cassandra.apache.org
[graphsense-transformation]: https://github.com/graphsense/graphsense-transformation