# -*- coding: utf-8 -*-
from datetime import datetime

import numpy as np
from cashaddress.convert import to_legacy_address
from psycopg2 import connect
from psycopg2.extensions import AsIs, register_adapter
from psycopg2.extras import execute_batch

from tagpack import ValidationError

register_adapter(np.int64, AsIs)


class TagStore(object):
    def __init__(self, url, schema):
        self.conn = connect(url, options=f"-c search_path={schema}")
        self.cursor = self.conn.cursor()

        self.cursor.execute("SELECT unnest(enum_range(NULL::currency))")
        self.supported_currencies = [i[0] for i in self.cursor.fetchall()]
        self.existing_packs = None
        self.existing_actorpacks = None

    def insert_taxonomy(self, taxonomy):
        if taxonomy.key == "confidence":
            self.insert_confidence_scores(taxonomy)
            return

        statement = "INSERT INTO taxonomy (id, source, description) "
        statement += "VALUES (%s, %s, %s)"
        desc = f"Imported at {datetime.now().isoformat()}"
        v = (taxonomy.key, taxonomy.uri, desc)
        self.cursor.execute(statement, v)

        for c in taxonomy.concepts:
            statement = "INSERT INTO concept (id, label, taxonomy, source, "
            statement += "description) VALUES (%s, %s, %s, %s, %s)"
            v = (c.id, c.label, c.taxonomy.key, c.uri, c.description)
            self.cursor.execute(statement, v)

        self.conn.commit()

    def insert_confidence_scores(self, confidence):
        statement = "INSERT INTO confidence (id, label, description, level)"
        statement += " VALUES (%s, %s, %s, %s)"

        for c in confidence.concepts:
            values = (c.id, c.label, c.description, c.level)
            self.cursor.execute(statement, values)

        self.conn.commit()

    def tp_exists(self, prefix, rel_path):
        if not self.existing_packs:
            self.existing_packs = self.get_ingested_tagpacks()
        return self.create_id(prefix, rel_path) in self.existing_packs

    def create_id(self, prefix, rel_path):
        return ":".join([prefix, rel_path]) if prefix else rel_path

    def insert_tagpack(
        self, tagpack, is_public, force_insert, prefix, rel_path, batch=1000
    ):

        tagpack_id = self.create_id(prefix, rel_path)
        h = _get_header(tagpack, tagpack_id)

        if force_insert:
            print(f"evicting and re-inserting tagpack {tagpack_id}")
            q = "DELETE FROM tagpack WHERE id = (%s)"
            self.cursor.execute(q, (tagpack_id,))

        q = "INSERT INTO tagpack \
            (id, title, description, creator, uri, is_public) \
            VALUES (%s,%s,%s,%s,%s,%s)"
        v = (
            h.get("id"),
            h.get("title"),
            h.get("description"),
            h.get("creator"),
            tagpack.uri,
            is_public,
        )
        self.cursor.execute(q, v)
        self.conn.commit()

        addr_sql = "INSERT INTO address (currency, address) VALUES (%s, %s) \
            ON CONFLICT DO NOTHING"
        tag_sql = "INSERT INTO tag (label, source, category, abuse, address, \
            currency, is_cluster_definer, confidence, lastmod, \
            context, tagpack, actor ) VALUES \
            (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"

        tag_data = []
        address_data = []
        for tag in tagpack.get_unique_tags():
            if self._supports_currency(tag):
                tag_data.append(_get_tag(tag, tagpack_id))
                address_data.append(_get_currency_and_address(tag))
            if len(tag_data) > batch:
                execute_batch(self.cursor, addr_sql, address_data)
                execute_batch(self.cursor, tag_sql, tag_data)

                tag_data = []
                address_data = []

        # insert remaining items
        execute_batch(self.cursor, addr_sql, address_data)
        execute_batch(self.cursor, tag_sql, tag_data)

        self.conn.commit()

    def actorpack_exists(self, prefix, actorpack_name):
        if not self.existing_actorpacks:
            self.existing_actorpacks = self.get_ingested_actorpacks()
        actorpack_id = self.create_actorpack_id(prefix, actorpack_name)
        return actorpack_id in self.existing_actorpacks

    def create_actorpack_id(self, prefix, actorpack_name):
        return ":".join([prefix, actorpack_name]) if prefix else actorpack_name

    def get_ingested_actorpacks(self) -> list:
        self.cursor.execute("SELECT id from actorpack")
        return [i[0] for i in self.cursor.fetchall()]

    def insert_actorpack(
        self, actorpack, is_public, force_insert, prefix, rel_path, batch=1000
    ):
        actorpack_id = self.create_actorpack_id(prefix, rel_path)
        h = _get_actor_header(actorpack, actorpack_id)

        if force_insert:
            print(f"Evicting and re-inserting actorpack {actorpack_id}")
            q = "DELETE FROM actorpack WHERE id = (%s)"
            self.cursor.execute(q, (actorpack_id,))

        q = "INSERT INTO actorpack \
            (id, title, creator, description, is_public, uri) \
            VALUES (%s,%s,%s,%s,%s,%s)"
        v = (
            h.get("id"),
            h.get("title"),
            h.get("creator"),
            h.get("description"),
            is_public,
            actorpack.uri,
        )
        self.cursor.execute(q, v)
        self.conn.commit()

        actor_sql = "INSERT INTO actor (id, label, context, uri, lastmod, actorpack) \
            VALUES (%s, %s, %s, %s, %s, %s)"
        act_cat_sql = "INSERT INTO actor_categories (actor_id, category_id) \
            VALUES (%s, %s)"
        act_jur_sql = "INSERT INTO actor_jurisdictions (actor_id, country_id) \
            VALUES (%s, %s)"

        actor_data = []
        cat_data = []
        jur_data = []
        for actor in actorpack.get_unique_actors():
            actor_data.append(_get_actor(actor, actorpack_id))
            cat_data.extend(_get_actor_categories(actor))
            jur_data.extend(_get_actor_jurisdictions(actor))

            # Handle writes in batches.
            if len(actor_data) > batch:
                execute_batch(self.cursor, actor_sql, actor_data)
                execute_batch(self.cursor, act_cat_sql, cat_data)
                execute_batch(self.cursor, act_jur_sql, jur_data)

                actor_data = []
                cat_data = []
                jur_data = []

        # insert remaining items (needed if written in batch and len(unique actors)
        # is not divisible by batch size)
        execute_batch(self.cursor, actor_sql, actor_data)
        execute_batch(self.cursor, act_cat_sql, cat_data)
        execute_batch(self.cursor, act_jur_sql, jur_data)

        self.conn.commit()

    def low_quality_address_labels(self, th=0.25, currency="", category="") -> dict:
        """
        This function returns a list of addresses having a quality meassure
        equal or lower than a threshold value, along with the corresponding
        tags for each address.
        """
        validate_currency(currency)
        currency = currency if currency else "%"
        category = category if category else "%"

        msg = "Threshold must be a float number between 0 and 1"
        try:
            th = float(th)
            if th < 0 or th > 1:
                raise ValidationError(msg)
        except ValueError:
            raise ValidationError(msg)

        q = "SELECT j.currency, j.address, array_agg(j.label) labels \
            FROM ( \
                SELECT q.currency, q.address, t.label \
                FROM address_quality q, tag t \
                WHERE t.category ILIKE %s \
                    AND t.address=q.address \
                    AND q.currency::text LIKE %s \
                    AND q.quality <= %s \
            ) as j \
            GROUP BY j.currency, j.address"

        self.cursor.execute(
            q,
            (
                category,
                currency,
                th,
            ),
        )

        return {(row[0], row[1]): row[2] for row in self.cursor.fetchall()}

    def remove_duplicates(self):
        self.cursor.execute(
            """
            DELETE
                FROM tag
                WHERE id IN
                (
                    SELECT id FROM
                        (SELECT
                            t.id,
                            t.address,
                            t.label,
                            t.source,
                            tp.creator,
                            ROW_NUMBER() OVER (PARTITION BY t.address,
                                t.label,
                                t.source,
                                tp.creator ORDER BY t.id DESC)
                                    AS duplicate_count
                        FROM
                            tag t,
                            tagpack tp
                        WHERE
                            t.tagpack = tp.id) as x
                    WHERE duplicate_count > 1
                )
            """
        )
        self.conn.commit()
        return self.cursor.rowcount

    def refresh_db(self):
        self.cursor.execute("REFRESH MATERIALIZED VIEW label")
        self.cursor.execute("REFRESH MATERIALIZED VIEW statistics")
        self.cursor.execute("REFRESH MATERIALIZED VIEW tag_count_by_cluster")
        self.cursor.execute(
            "REFRESH MATERIALIZED VIEW "
            "cluster_defining_tags_by_frequency_and_maxconfidence"
        )  # noqa
        self.conn.commit()

    def get_addresses(self, update_existing):
        if update_existing:
            self.cursor.execute("SELECT address, currency FROM address")
        else:
            q = "SELECT address, currency FROM address WHERE NOT is_mapped"
            self.cursor.execute(q)
        for record in self.cursor:
            yield record

    def get_tagstore_composition(self, by_currency=False):
        if by_currency:
            self.cursor.execute(
                "SELECT creator, "
                "category, "
                "tp.is_public as is_public, "
                "t.currency as currency, "
                "count(distinct t.label) as labels_count, "
                "count(*) as tags_count "
                "FROM tag t, tagpack tp where t.tagpack = tp.id "
                "group by currency, creator, category, is_public;"
            )
        else:
            self.cursor.execute(
                "SELECT creator, "
                "category, "
                "tp.is_public as is_public, "
                "count(distinct t.label) as labels_count, "
                "count(*) as tags_count "
                "FROM tag t, tagpack tp where t.tagpack = tp.id "
                "group by creator, category, is_public;"
            )

        for record in self.cursor:
            yield record

    def insert_cluster_mappings(self, clusters):
        if not clusters.empty:
            q = "INSERT INTO address_cluster_mapping (address, currency, \
                gs_cluster_id , gs_cluster_def_addr , gs_cluster_no_addr) \
                VALUES (%s, %s, %s, %s, %s) ON CONFLICT (currency, address) \
                DO UPDATE SET gs_cluster_id = EXCLUDED.gs_cluster_id, \
                gs_cluster_def_addr = EXCLUDED.gs_cluster_def_addr, \
                gs_cluster_no_addr = EXCLUDED.gs_cluster_no_addr"

            cols = [
                "address",
                "currency",
                "cluster_id",
                "cluster_defining_address",
                "no_addresses",
            ]
            data = clusters[cols].to_records(index=False)

            execute_batch(self.cursor, q, data)
            self.conn.commit()

    def _supports_currency(self, tag):
        return tag.all_fields.get("currency") in self.supported_currencies

    def finish_mappings_update(self, keys):
        q = "UPDATE address SET is_mapped=true WHERE NOT is_mapped \
                AND currency IN %s"
        self.cursor.execute(q, (tuple(keys),))
        self.conn.commit()

    def get_ingested_tagpacks(self) -> list:
        self.cursor.execute("SELECT id from tagpack")
        return [i[0] for i in self.cursor.fetchall()]

    def get_quality_measures(self, currency="") -> dict:
        """
        This function returns a dict with the quality measures (count, avg, and
        stddev) for a specific currency, or for all if currency is not
        specified.
        """
        validate_currency(currency)

        query = "SELECT COUNT(quality), AVG(quality), STDDEV(quality)"
        query += " FROM address_quality"
        if currency:
            query += " WHERE currency=%s"
            self.cursor.execute(query, (currency,))
        else:
            self.cursor.execute(query)

        keys = ["count", "avg", "stddev"]
        return {keys[i]: v for row in self.cursor.fetchall() for i, v in enumerate(row)}

    def calculate_quality_measures(self) -> dict:
        self.cursor.execute("CALL calculate_quality(FALSE)")
        self.cursor.execute("CALL insert_address_quality()")
        self.conn.commit()
        return self.get_quality_measures()

    def list_tags(self, unique=False, category="", currency=""):
        validate_currency(currency)
        currency = currency if currency else "%"
        category = category if category else "%"

        q = (
            f"SELECT {'DISTINCT' if unique else ''} "
            "t.currency, tp.title, t.label "
            "FROM tagpack tp, tag t WHERE t.tagpack = tp.id "
            "AND t.category ILIKE %s AND t.currency::text LIKE %s "
            "ORDER BY t.currency, tp.title, t.label ASC"
        )
        v = (category, currency)
        self.cursor.execute(q, v)
        return self.cursor.fetchall()

    def list_actors(self, category=""):
        category = category if category else "%"

        q = (
            "SELECT a.actorpack, a.id, a.label, c.label "
            "FROM actor a, actor_categories ac, concept c "
            "WHERE ac.actor_id = a.id AND ac.category_id = c.id "
            "AND c.label ILIKE %s "
            "ORDER BY a.id ASC"
        )
        v = (category,)
        self.cursor.execute(q, v)
        return self.cursor.fetchall()

    def list_address_actors(self, currency=""):
        validate_currency(currency)
        currency = currency if currency else "%"
        q = (
            "SELECT t.id, t.label, t.address, t.category, a.label "
            "FROM tag t, actor a "
            "WHERE t.label = a.id "
            "AND t.currency::text LIKE %s"
        )
        v = (currency,)
        self.cursor.execute(q, v)
        return self.cursor.fetchall()

    def update_tags_actors(self):
        """
        Update the `tag.actor` field by searching an actor.id that matches with
        the `tag.label`. Tags marked as abuse are excluded from the update.
        """
        # TODO this is a test actor list
        actors = """
        'bitmex', 'bitfinex', 'huobi', 'binance', 'coinbase', 'zaif',
        'mtgox', 'okx', 'poloniex', 'kucoin', 'kraken', 'bitstamp', 'bithumb',
        'shapeshift', 'deribit', 'gemini', 'f2pool', 'bittrex', 'crypto.com',
        'coinmetro', 'bter.com', 'cryptopia', 'hitbtc', 'paribu', 'gate.io',
        '0x', '1inch', 'aave', 'badger', 'balancer', 'barnbridge', 'compound',
        'convex', 'curvefinance', 'dydx', 'fei', 'futureswap',
        'harvestfinance', 'hegic', 'instadapp', 'maker', 'nexus', 'renvm',
        'sushiswap', 'synthetix', 'uniswap', 'vesper', 'yearn'
        """
        q = (
            "UPDATE tag SET actor=a.id "
            f"FROM (SELECT id FROM actor WHERE id in ({actors})) a "
            "WHERE tag.abuse IS NULL "
            "AND tag.label ILIKE CONCAT(a.id, '%')"
        )
        # "AND tag.label NOT LIKE 'upbit hack%' "\
        self.cursor.execute(q)
        rowcount = self.cursor.rowcount
        # This query is to normalize OKEX/OKX/OKB tags
        q = (
            "UPDATE tag SET actor='okx' "
            "WHERE abuse IS NULL "
            "AND (label ILIKE 'okex%' OR label ILIKE 'okb%')"
        )
        self.cursor.execute(q)
        self.conn.commit()
        return rowcount

    def update_quality_actors(self):
        """
        Update all entries in `address_quality` having a unique actor in table
        `tag`. The corresponding quality is 1, due to the conflicts are solved.
        """
        # q = "SELECT t.currency, t.address, COUNT(t.actor) n" \
        #     "FROM tag t, address_quality q" \
        #     "WHERE t.currency=q.currency" \
        #     "AND t.address=q.address" \
        #     "AND NOT t.actor IS NULL" \
        #     "GROUP BY t.currency, t.address, t.actor"

        q = (
            "UPDATE address_quality "
            "SET "
            "n_tags=1, "
            "n_dif_tags=1, "
            "total_pairs=0, "
            "q1=0, "
            "q2=0, "
            "q3=0, "
            "q4=0, "
            "quality=1.0 "
            "FROM ("
            "SELECT currency, address "
            "FROM tag "
            "WHERE NOT actor IS NULL "
            "GROUP BY currency, address "
            "HAVING COUNT(DISTINCT actor) = 1 "
            ") s "
            "WHERE address_quality.currency=s.currency "
            "AND address_quality.address=s.address"
        )
        self.cursor.execute(q)
        rowcount = self.cursor.rowcount
        self.conn.commit()
        return rowcount


def validate_currency(currency):
    currency = currency.upper()
    if currency not in ["", "BCH", "BTC", "ETH", "LTC", "ZEC"]:
        raise ValidationError(f"Currency not supported: {currency}")


def _get_tag(tag, tagpack_id):
    label = tag.all_fields.get("label").lower().strip()
    lastmod = tag.all_fields.get("lastmod", datetime.now().isoformat())

    _, address = _get_currency_and_address(tag)

    return (
        label,
        tag.all_fields.get("source"),
        tag.all_fields.get("category", None),
        tag.all_fields.get("abuse", None),
        address,
        tag.all_fields.get("currency"),
        tag.all_fields.get("is_cluster_definer"),
        tag.all_fields.get("confidence"),
        lastmod,
        tag.all_fields.get("context"),
        tagpack_id,
        tag.all_fields.get("actor", None),
    )


def _perform_address_modifications(address, curr):
    if "BCH" == curr.upper() and address.startswith("bitcoincash"):
        address = to_legacy_address(address)

    elif "ETH" == curr.upper():
        address = address.lower()

    return address


def _get_currency_and_address(tag):
    curr = tag.all_fields.get("currency")
    addr = tag.all_fields.get("address")

    addr = _perform_address_modifications(addr, curr)

    return curr, addr


def _get_header(tagpack, tid):
    tc = tagpack.contents
    return {
        "id": tid,
        "title": tc["title"],
        "creator": tc["creator"],
        "description": tc.get("description", "not provided"),
    }


def _get_actor_header(actorpack, id):
    ac = actorpack.contents
    return {
        "id": id,
        "title": ac["title"],
        "creator": ac["creator"],
        "description": ac.get("description", "not provided"),
    }


def _get_actor(actor, actorpack_id):
    uri = actor.all_fields.get("uri", None)
    context = actor.all_fields.get("context", None)
    return (
        actor.all_fields.get("id"),
        actor.all_fields.get("label", "").strip(),
        context.strip() if context is not None else context,
        uri.strip() if uri is not None else uri,
        actor.all_fields.get("lastmod", datetime.now().isoformat()),
        actorpack_id,
    )


def _get_actor_categories(actor):
    data = []
    actor_id = actor.all_fields.get("id")
    for category in actor.all_fields.get("categories"):
        data.append((actor_id, category))
    return data


def _get_actor_jurisdictions(actor):
    data = []
    actor_id = actor.all_fields.get("id")
    for country in actor.all_fields.get("jurisdictions"):
        data.append((actor_id, country))
    return data
