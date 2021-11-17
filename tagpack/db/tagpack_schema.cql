DROP KEYSPACE IF EXISTS KEYSPACE_NAME;

CREATE KEYSPACE KEYSPACE_NAME
WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 3 };

USE KEYSPACE_NAME;


CREATE TABLE tagpack_by_uri (
    uri                 text PRIMARY KEY,
    title               text,
    description         text,
    owner               text,
    creator             text,
    is_public           boolean
);

CREATE TABLE address_tag_by_address (
    address             text,
    currency            text,
    label               text,
    source              text,
    tagpack_uri         text,
    confidence          int,
    is_cluster_definer  boolean,
    created             date,
    lastmod             date,
    category            text,
    abuse               text,
    PRIMARY KEY (address, currency, label, source, tagpack_uri)
);

CREATE TABLE entity_tag_by_id (
    entity              int,
    currency            text,
    label               text,
    source              text,
    tagpack_uri         text,
    confidence          int,
    created             date,
    lastmod             date,
    category            text,
    abuse               text,
    PRIMARY KEY (entity, currency, label, source, tagpack_uri)
);

CREATE TABLE taxonomy_by_key (
    key                 text,
    uri                 text,
    PRIMARY KEY (key)
);

CREATE TABLE concept_by_taxonomy_id (
    taxonomy            text,
    id                  text,
    uri                 text,
    label               text,
    description         text,
    PRIMARY KEY (taxonomy, id)
);