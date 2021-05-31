"""Cassandra - Handles ingest into Apache Cassandra"""

import importlib.resources as pkg_resources

from cassandra.cluster import Cluster
from cassandra.concurrent import execute_concurrent

from . import db
from tagpack import StorageError
from tagpack.tagpack import AddressTag, EntityTag

CONCURRENCY = 100
DEFAULT_TIMEOUT = 60

SCHEMA_FILE = 'tagpack_schema.cql'
KEYPACE_PACEHOLDER = 'KEYSPACE_NAME'


class Cassandra(object):
    """Cassandra Back-end Connector

    Taxonomies and TagPacks can be ingested into Apache Cassandra
    for further processing within GraphSense.

    This class provides the necessary schema creation and data
    ingesting functions.

    """

    def __init__(self, db_node):
        self.db_node = db_node

    def connect(self):
        """Connect to the given Cassandra cluster nodes"""
        self.cluster = Cluster([self.db_node])
        try:
            self.session = self.cluster.connect()
            self.session.default_timeout = DEFAULT_TIMEOUT
        except Exception as e:
            raise StorageError("Cannot connect to {}".format(self.db_node), e)

    def setup_keyspace(self, keyspace):
        """Setup keyspace and tables"""
        if not self.session:
            raise StorageError("Session not available. Call connect() first")

        schema = pkg_resources.read_text(db, SCHEMA_FILE)

        # Replace keyspace name placeholder in CQL schema script
        schema = schema.replace(KEYPACE_PACEHOLDER, keyspace)

        statements = schema.split(';')
        for stmt in statements:
            if len(stmt) > 0:
                stmt = stmt + ';'
                self.session.execute(stmt)

    def has_keyspace(self, keyspace):
        """Check whether a given keyspace is present in the cluster"""
        if not self.session:
            raise StorageError("Session not availble. Call connect() first")
        try:
            query = 'SELECT keyspace_name FROM system_schema.keyspaces'
            result = self.session.execute(query)
            keyspaces = [row.keyspace_name for row in result]
            return keyspace in keyspaces
        except Exception as e:
            raise StorageError("Error when executing {}".format(query), e)

    def insert_taxonomy(self, taxonomy, keyspace):
        """Insert a taxonomy into a given keyspace"""
        if not self.session:
            raise StorageError("Session not available. Call connect() first")
        try:
            self.session.set_keyspace(keyspace)
            query = "INSERT INTO taxonomy_by_key JSON '{}';".format(
                taxonomy.to_json())
            self.session.execute(query)
            for concept in taxonomy.concepts:
                concept_json = concept.to_json()
                query = "INSERT INTO concept_by_taxonomy_id JSON '{}';".format(
                    concept_json.replace("'", ""))
                self.session.execute(query)
        except Exception as e:
            raise StorageError("Taxonomy insertion error", e)

    def insert_tagpack(self, tagpack, keyspace, concurrency):
        """Insert a tagpack into a given keyspace"""
        if not self.session:
            raise StorageError("Session not available. Call connect() first")
        try:
            self.session.set_keyspace(keyspace)

            tagpack_json = tagpack.to_json()
            # tagpack_json = Cassandra.fields_to_timestamp(tagpack_json)

            q = f"INSERT INTO tagpack_by_uri JSON '{tagpack_json}'"
            self.session.execute(q)

            stmt_addr = self.session.prepare(
                "INSERT INTO address_tag_by_address JSON ?")

            stmt_entity = self.session.prepare(
                "INSERT INTO entity_tag_by_id JSON ?")

            statements_and_params = []

            for tag in tagpack.tags:
                # prepare statements for table tag_by_address
                params = (tag.to_json(), )
                if isinstance(tag, AddressTag):
                    statements_and_params.append((stmt_addr, params))
                elif isinstance(tag, EntityTag):
                    statements_and_params.append((stmt_entity, params))
                else:
                    raise StorageError(
                        "Invalid tag: must be either Address or EntiyTag")

            results = execute_concurrent(self.session, statements_and_params,
                                         concurrency=concurrency,
                                         raise_on_first_error=True)
            for (success, result) in results:
                if not success:
                    raise StorageError(
                        f"Error when inserting tagpack {tagpack.filename}")

        except Exception as e:
            raise StorageError("TagPack insertion error", e)

    def close(self):
        """Closes the Apache Cassandra cluster connection"""
        self.cluster.shutdown()
