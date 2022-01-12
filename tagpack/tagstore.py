# -*- coding: utf-8 -*-
import os
from datetime import datetime

import numpy as np
from psycopg2 import connect
from psycopg2.extensions import register_adapter, AsIs
from psycopg2.extras import execute_batch

register_adapter(np.int64, AsIs)


class TagStore(object):
    def __init__(self, url, schema):
        self.conn = connect(url, options=f"-c search_path={schema}")
        self.cursor = self.conn.cursor()

        self.cursor.execute("SELECT unnest(enum_range(NULL::currency))")
        self.supported_currencies = [i[0] for i in self.cursor.fetchall()]

    def insert_taxonomy(self, taxonomy):
        self.cursor.execute("""INSERT INTO taxonomy (id, source, description) VALUES (%s, %s, %s)""", (taxonomy.key, taxonomy.uri, f"Imported at {datetime.now().isoformat()}"))

        for c in taxonomy.concepts:
            self.cursor.execute("""INSERT INTO concept (id, label, taxonomy, source, description) VALUES (%s, %s, %s, %s, %s)""", (c.id, c.label, c.taxonomy.key, c.uri, c.description))

        self.conn.commit()

    def insert_tagpack(self, tagpack, batch=1000):
        tagpack_id = _get_id(tagpack)
        h = _get_header(tagpack, tagpack_id)

        self.cursor.execute("INSERT INTO tagpack (id, title, description, creator, owner, source) VALUES (%s, %s,%s,%s,%s,%s)", (h.get('id'), h.get('title'), h.get('description'), h.get('creator'), h.get('owner'), h.get('source')))
        self.conn.commit()

        addr_sql = "INSERT INTO address (currency, address) VALUES (%s, %s) ON CONFLICT DO NOTHING"
        tag_sql = "INSERT INTO tag (label, source, category, abuse, address, currency, is_cluster_definer, confidence, lastmod, tagpack ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"

        tag_data = []
        address_data = []
        for tag in tagpack.tags:
            if self._should_insert(tag):
                tag_data.append(_get_tag(tag, tagpack_id))
                address_data.append(_get_address(tag))
            if len(tag_data) > batch:
                execute_batch(self.cursor, addr_sql, address_data)
                execute_batch(self.cursor, tag_sql, tag_data)

                tag_data = []
                address_data = []

        # insert remaining items
        execute_batch(self.cursor, addr_sql, address_data)
        execute_batch(self.cursor, tag_sql, tag_data)

        self.cursor.execute('REFRESH MATERIALIZED VIEW label')
        self.conn.commit()

    def get_addresses(self):
        self.cursor.execute("SELECT address, currency FROM address")
        for record in self.cursor:
            yield record

    def insert_cluster_mappings(self, clusters):
        q = "INSERT INTO address_cluster_mapping (address, currency, gs_cluster_id , gs_cluster_def_addr , gs_cluster_no_addr , gs_cluster_in_degr , gs_cluster_out_degr)" \
            "VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING"

        data = clusters[['address', 'currency', 'cluster_id', 'cluster_defining_address', 'no_addresses', 'in_degree', 'out_degree']].to_records(index=False)

        execute_batch(self.cursor, q, data)
        self.conn.commit()

    def _should_insert(self, tag):
        return tag.all_fields.get('currency') in self.supported_currencies


def _get_tag(tag, tagpack_id):
    label = tag.all_fields.get('label').lower().strip()

    return (label, tag.all_fields.get('source'), tag.all_fields.get('category', None),
            tag.all_fields.get('abuse', None), tag.all_fields.get('address'), tag.all_fields.get('currency'),
            tag.all_fields.get('is_cluster_definer'), tag.all_fields.get('confidence'), tag.all_fields.get('lastmod'), tagpack_id)


def _get_address(tag):
    return tag.all_fields.get('currency'), tag.all_fields.get('address')


def _get_id(tagpack):
    return os.path.split(tagpack.uri)[1]


def _get_header(tagpack, tid):
    tc = tagpack.contents
    return {
        'id': tid,
        'title': tc['title'],
        'source': tc.get('source', os.path.split(tagpack.tags[0].all_fields.get('source'))[0]),
        'creator': tc['creator'],
        'description': tc.get('description', 'not provided'),
        'owner': tc.get('owner', 'unknown')}

