# -*- coding: utf-8 -*-
import textwrap
from datetime import datetime
from functools import wraps
from typing import List

import numpy as np
from cashaddress.convert import to_legacy_address
from psycopg2 import connect
from psycopg2.extensions import AsIs, register_adapter
from psycopg2.extras import execute_batch, execute_values

from tagpack import ValidationError
from tagpack.cmd_utils import print_warn
from tagpack.constants import KNOWN_NETWORKS
from tagpack.utils import get_github_repo_url

register_adapter(np.int64, AsIs)


def auto_commit(function):
    @wraps(function)
    def wrapper(*args, **kwargs):
        """
        Automatically calls commit at the end of a function or
        rollback if an error occurs. If rollback is not execute
        int leaves the connection in a broken state.
        https://stackoverflow.com/questions/2979369/databaseerror-current-transaction-is-aborted-commands-ignored-until-end-of-tra
        """
        self, *_ = args
        try:
            output = function(*args, **kwargs)
        except Exception as e:
            # self.cursor.execute("rollback")
            self.conn.rollback()
            raise e
        finally:
            self.conn.commit()
        return output

    return wrapper


def _private_condition(show_private: bool, table: str):
    return f"and {table}.is_public=true" if not show_private else ""


class TagStore(object):
    def __init__(self, url, schema):
        self.conn = connect(url, options=f"-c search_path={schema}")
        self.cursor = self.conn.cursor()
        self.existing_packs = None
        self.existing_actorpacks = None

    @auto_commit
    def insert_taxonomy(self, taxonomy):
        if taxonomy.key == "confidence":
            self.insert_confidence_scores(taxonomy)
            return

        statement = (
            "INSERT INTO taxonomy (id, source, description) "
            "VALUES (%(id)s, %(source)s, %(description)s)"
            "ON CONFLICT (id) DO UPDATE "
            "SET (source, description) = "
            "(%(source)s, %(description)s);"
        )

        desc = f"Imported at {datetime.now().isoformat()}"
        self.cursor.execute(
            statement, {"id": taxonomy.key, "source": taxonomy.uri, "description": desc}
        )

        statement = (
            "INSERT INTO concept (id, label, taxonomy, source, description) "
            "VALUES (%(id)s,%(label)s,%(taxonomy)s,%(source)s,%(description)s)"
            "ON CONFLICT (id) DO UPDATE "
            "SET (label, taxonomy, source, description) = "
            "(%(label)s,%(taxonomy)s,%(source)s,%(description)s);"
        )
        for c in taxonomy.concepts:
            v = {
                "id": c.id,
                "label": c.label,
                "taxonomy": c.taxonomy.key,
                "source": c.uri,
                "description": c.description,
            }
            self.cursor.execute(statement, v)

    @auto_commit
    def insert_confidence_scores(self, confidence):
        statement = (
            "INSERT INTO confidence (id, label, description, level)"
            " VALUES (%(id)s,%(label)s,%(description)s,%(level)s)"
            "ON CONFLICT (id) DO UPDATE "
            "SET (label, description, level) = "
            "(%(label)s,%(description)s,%(level)s);"
        )

        for c in confidence.concepts:
            self.cursor.execute(
                statement,
                {
                    "id": c.id,
                    "label": c.label,
                    "description": c.description,
                    "level": c.level,
                },
            )

    def tp_exists(self, prefix, rel_path):
        if not self.existing_packs:
            self.existing_packs = self.get_ingested_tagpacks()
        return self.create_id(prefix, rel_path) in self.existing_packs

    def create_id(self, prefix, rel_path):
        return ":".join([prefix, rel_path]) if prefix else rel_path

    @auto_commit
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

        addr_sql = "INSERT INTO address (network, address) VALUES %s \
            ON CONFLICT DO NOTHING"
        tag_sql = "INSERT INTO tag (label, source, category, abuse, address, \
            currency, network, is_cluster_definer, confidence, lastmod, \
            context, tagpack, actor ) VALUES \
            %s RETURNING id"

        tag_concept_sql = "INSERT INTO tag_concept (tag_id, concept_id) VALUES %s \
            ON CONFLICT DO NOTHING"

        def insert_tags_batch(tag_data, tag_concepts, address_data):
            execute_values(self.cursor, addr_sql, address_data, template="(%s, %s)")
            new_ids = execute_values(
                self.cursor,
                tag_sql,
                tag_data,
                template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                fetch=True,
                page_size=batch,
            )

            assert len(tag_concepts) == len(new_ids)
            tcd = []
            for tag_id, concept_ids in zip(new_ids, tag_concepts):
                for tc in concept_ids:
                    tcd.append((tag_id, tc))
            execute_values(self.cursor, tag_concept_sql, tcd, template="(%s, %s)")

        tag_data = []
        address_data = []
        tag_concepts = []
        for tag in tagpack.get_unique_tags():
            tag_data.append(_get_tag(tag, tagpack_id))
            address_data.append(_get_network_and_address(tag))
            tag_concepts.append(_get_tag_concepts(tag))

            if len(tag_data) > batch:
                insert_tags_batch(tag_data, tag_concepts, address_data)
                tag_data = []
                address_data = []
                tag_concepts = []

        # insert remaining items
        insert_tags_batch(tag_data, tag_concepts, address_data)

    def actorpack_exists(self, prefix, actorpack_name):
        if not self.existing_actorpacks:
            self.existing_actorpacks = self.get_ingested_actorpacks()
        actorpack_id = self.create_actorpack_id(prefix, actorpack_name)
        return actorpack_id in self.existing_actorpacks

    def create_actorpack_id(self, prefix, actorpack_name):
        return ":".join([prefix, actorpack_name]) if prefix else actorpack_name

    def get_ingested_actorpacks(self) -> List:
        self.cursor.execute("SELECT id from actorpack")
        return [i[0] for i in self.cursor.fetchall()]

    @auto_commit
    def insert_actorpack(
        self, actorpack, is_public, force_insert, prefix, rel_path, batch=1000
    ):
        actorpack_id = self.create_actorpack_id(prefix, rel_path)
        h = _get_actor_header(actorpack, actorpack_id)

        if force_insert:
            print(f"Evicting and re-inserting actorpack {actorpack_id}")
            q = "DELETE FROM actorpack WHERE id = (%s)"
            self.cursor.execute(q, (actorpack_id,))

        q = (
            "INSERT INTO actorpack "
            "(id, title, creator, description, is_public, uri) "
            "VALUES "
            "(%(id)s,%(title)s,%(creator)s,%(description)s,%(is_public)s,%(uri)s) "
            "ON CONFLICT (id) DO UPDATE "
            "SET (title, creator, description, is_public, uri) = "
            "(%(title)s,%(creator)s,%(description)s,%(is_public)s,%(uri)s);"
        )
        v = {
            "id": h.get("id"),
            "title": h.get("title"),
            "creator": h.get("creator"),
            "description": h.get("description"),
            "is_public": is_public,
            "uri": actorpack.uri,
        }
        self.cursor.execute(q, v)
        self.conn.commit()

        actor_sql = (
            "INSERT INTO actor (id, label, context, uri, lastmod, actorpack) "
            "VALUES (%(id)s,%(label)s,%(context)s,%(uri)s,%(lastmod)s,%(actorpack)s) "
            "ON CONFLICT (id) DO UPDATE "
            "SET (label, context, uri, lastmod, actorpack) = "
            "(%(label)s,%(context)s,%(uri)s,%(lastmod)s,%(actorpack)s);"
        )

        act_cat_sql = (
            "INSERT INTO actor_categories (actor_id, category_id) "
            "VALUES (%(actor_id)s, %(category_id)s) "
            "ON CONFLICT (actor_id, category_id) DO NOTHING;"
        )
        act_jur_sql = (
            "INSERT INTO actor_jurisdictions (actor_id, country_id) "
            "VALUES (%(actor_id)s, %(country_id)s) "
            "ON CONFLICT (actor_id, country_id) DO NOTHING;"
        )

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

    def find_actors_for(
        self,
        label,
        max_results,
        threshold=0.2,
        search_columns=["id", "label", "uri"],
        use_simple_similarity=True,
    ):
        fields = ["id", "label", "uri", "context"]
        fields_output = fields + ["similarity"]
        fields_str = ",".join(fields)
        search_target = f"concat_ws(' ',{','.join(search_columns)})"

        if use_simple_similarity:
            similarity_query = textwrap.dedent(
                f"""SELECT
                    {fields_str},
                    similarity(%(label)s, {search_target}) as similarity
                    FROM actor
                    WHERE similarity(%(label)s, {search_target}) > %(threshold)s
                    ORDER BY similarity DESC
                    LIMIT %(max_results)s"""
            )
        else:
            similarity_query = textwrap.dedent(
                f"""SELECT
                    {fields_str},
                    (simple_similarity + word_similarity + strict_word_similarity)
                     / 3 as similarity
                    FROM (
                        SELECT {fields_str},
                        similarity(%(label)s,{search_target}) as simple_similarity,
                        word_similarity(%(label)s,{search_target})as word_similarity,
                        strict_word_similarity(%(label)s,{search_target})
                        as strict_word_similarity
                        FROM actor
                    ) blub
                    WHERE
                    (simple_similarity + word_similarity + strict_word_similarity) / 3
                    > %(threshold)s
                    ORDER BY similarity DESC
                    LIMIT %(max_results)s"""
            )

        self.cursor.execute(
            similarity_query,
            {"label": label, "threshold": threshold, "max_results": max_results},
        )

        return [
            {k: v for k, v in zip(fields_output, x)}  # noqa: C416
            for x in self.cursor.fetchall()
        ]

    def addresses_with_actor_collisions(self) -> List[dict]:
        fields_output = ["address", "actors"]
        query = (
            "SELECT agg.address, agg.actors from "
            "(SELECT "
            "   address, "
            "   count(distinct tag.actor) as ac, "
            "   string_agg(tag.actor, ', ') as actors "
            " from tag group by tag.address) as agg "
            "where agg.ac > 1"
        )

        self.cursor.execute(query)

        def uniq_actor(d):
            d["actors"] = ", ".join(set(d["actors"].split(", ")))
            return d

        return [
            uniq_actor({k: v for k, v in zip(fields_output, x)})  # noqa: C416
            for x in self.cursor.fetchall()
        ]

    def get_actors_with_jurisdictions(
        self, category="", max_results=5, include_not_used=False
    ) -> List[dict]:
        fields = ["actor.id", "actor.label", "actor.uri", "actor.context"]
        fields_str = ",".join(fields)
        fields_output = fields + ["categories", "jurisdictions", "#tags"]
        params = {
            "max_results": max_results,
        }

        cat_clause = ""
        if len(category) > 0:
            params["category"] = category.strip()
            cat_clause = "and actor_categories.category_id = %(category)s "

        actor_join = "LEFT OUTER JOIN " if include_not_used else "INNER JOIN"

        query = (
            f"SELECT {fields_str} "
            ", string_agg(actor_categories.category_id, ', ') as categories  "
            ", string_agg(actor_jurisdictions.country_id, ', ') as jurisdictions  "
            ", count(distinct tag.id) as nr_tags  "
            "FROM actor "
            f"{actor_join} tag on actor.id = tag.actor "
            "INNER JOIN actor_categories on actor.id = actor_categories.actor_id "
            "LEFT OUTER JOIN "
            "actor_jurisdictions on actor.id = actor_jurisdictions.actor_id "
            "WHERE "
            "actor_jurisdictions.country_id is NULL "
            f"{cat_clause} "
            "GROUP BY actor.id "
            "ORDER BY nr_tags DESC "
            "LIMIT %(max_results)s"
        )

        self.cursor.execute(query, params)

        def format_value(k, v):
            if k == "categories" or k == "jurisdictions" and v:
                return ", ".join(set(v.split(", ")))
            else:
                return v

        return [
            {k: format_value(k, v) for k, v in zip(fields_output, x)}
            for x in self.cursor.fetchall()
        ]

    def top_labels_without_actor(self, category="", max_results=5) -> List[dict]:
        fields = ["tag.label"]
        fields_str = ",".join(fields)
        fields_output = fields + ["count", "tagpacks"]
        params = {
            "max_results": max_results,
        }

        cat_clause = ""
        if len(category) > 0:
            params["category"] = category.strip()
            cat_clause = "and tag.category = %(category)s "

        query = (
            f"SELECT {fields_str}, "
            "count(tag.id) as count, "
            "string_agg(tagpack.uri,', ') as tagpacks "
            "FROM tag "
            "INNER JOIN tagpack on tagpack.id = tag.tagpack "
            "WHERE actor is NULL "
            f"{cat_clause} "
            "GROUP BY tag.label "
            "ORDER BY count DESC "
            "LIMIT %(max_results)s"
        )

        self.cursor.execute(query, params)

        def format_value(k, v):
            if k == "tagpacks" and v:
                return ", ".join(set(v.split(", ")))
            else:
                return v

        return [
            {k: format_value(k, v) for k, v in zip(fields_output, x)}
            for x in self.cursor.fetchall()
        ]

    def _result(self, query, params=None, page=0, pagesize=None):
        if pagesize:
            query += f" LIMIT {pagesize}"
        query += f" OFFSET {page*pagesize if pagesize else 0}"
        print(query, params)
        self.cursor.execute(query, params)

        return [
            dict(zip([column[0] for column in self.cursor.description], row))
            for row in self.cursor.fetchall()
        ]

    def tagstore_source_repos(self) -> List[dict]:
        fields = ["uri"]
        query = f"SELECT {','.join(fields)} FROM tagpack"

        self.cursor.execute(query)

        def get_repo_part(url):
            rp = get_github_repo_url(url)
            return rp or url

        repos = {get_repo_part(x[0]) for x in self.cursor.fetchall()}

        return [{k: v for k, v in zip(fields, [x])} for x in repos]  # noqa: C416

    def taxonomies(self):
        fields = ["id", "source", "description"]

        query = f"SELECT {','.join(fields)} FROM taxonomy "

        return self._result(query)

    def concepts(self, taxonomy: str):
        query = f"SELECT * FROM concept WHERE taxonomy = '{taxonomy}'"

        return self._result(query)

    def count_labels_by_network(self, network: str):
        query = f"""
            select
                no_labels,
                no_implicit_tagged_addresses as no_tagged_addresses
            from
                statistics tp
            where
                network = '{network.upper()}'"""

        return self._result(query)

    def count_labels_by_entity(self, network, entity):
        query = """
            select sum(count) as count from tag_count_by_cluster
            where
               network = %s
               and gs_cluster_id = %s """

        return self._result(query, params=[network.upper(), entity])

    def tags_by_label(self, label: str, private: bool, page, pagesize):
        query = f"""SELECT
                t.*,
                tp.uri,
                tp.uri,
                tp.creator,
                tp.title,
                tp.is_public,
                c.level,
                acm.gs_cluster_id
            FROM
               tag t,
               tagpack tp,
               confidence c,
               address_cluster_mapping acm
           WHERE
               t.tagpack = tp.id
               AND t.confidence = c.id
               AND acm.address=t.address
               AND acm.network=t.network
               {_private_condition(private, "tp")}
               AND t.label = %s """

        return self._result(query, [label], page, pagesize)

    def tags_by_address(self, address, private, page, pagesize):
        query = f"""select
                    t.*,
                    tp.uri,
                    tp.creator,
                    tp.title,
                    tp.is_public,
                    c.level,
                    acm.gs_cluster_id
                from
                    tag t,
                    tagpack tp,
                    confidence c,
                    address_cluster_mapping acm
                where
                    t.tagpack=tp.id
                    and c.id=t.confidence
                    and t.address = %s
                    and acm.address=t.address
                    and acm.network=t.network
                    {_private_condition(private, "tp")}
                order by
                    c.level DESC, t.id ASC
                    """

        return self._result(query, [address], page, pagesize)

    def labels(self, search_string, private, limit):
        query = f"""select
                t.label
               from
                tag t,
                label l,
                tagpack tp
               where
                t.label = l.label
                and tp.id = t.tagpack
                and similarity(l.label, %s) > 0.2
                {_private_condition(private, "tp")}
               order by l.label <-> %s
               limit %s"""

        return self._result(query, [search_string, search_string, limit])

    def tags_by_entity(self, network, cluster_id, private, page, pagesize):
        query = f"""select
                   t.*,
                   tp.uri,
                   tp.creator,
                   tp.title,
                   tp.is_public,
                   c.level,
                   acm.gs_cluster_id
               from
                   tag t,
                   tagpack tp,
                   address_cluster_mapping acm,
                   confidence c
               where
                   acm.address=t.address
                   and acm.network=t.network
                   and c.id=t.confidence
                   and t.network = %s
                   and acm.gs_cluster_id = %s
                   {_private_condition(private, "tp")}
                   and t.tagpack=tp.id
               order by
                   c.level desc,
                   t.address asc
                   """

        return self._result(
            query,
            [network.upper(), cluster_id],
            page,
            pagesize,
        )

    def best_entity_tag(self, network, cluster_id, private):
        if network == "eth":
            # in case of eth we want to propagate the best address tag
            # regardless of if the tagpack is a defines it as cluster definer
            # since cluster == entity in eth
            cluster_definer_condition = ""
        else:
            cluster_definer_condition = """and
                            (cd.is_cluster_definer=true
                                AND t.is_cluster_definer=true
                            OR
                            cd.is_cluster_definer=false
                                AND t.is_cluster_definer!=true
                        )"""

        query = f"""select
                        t.*,
                        tp.uri,
                        tp.creator,
                        tp.title,
                        tp.is_public,
                        cd.gs_cluster_id,
                        c.level
                   from
                        tag t,
                        tagpack tp,
                        address_cluster_mapping acm,
                        cluster_defining_tags_by_frequency_and_maxconfidence cd,
                        confidence c
                   where
                        cd.gs_cluster_id=acm.gs_cluster_id
                        and cd.network = acm.network
                        and cd.label = t.label
                        and cd.max_level = c.level
                        and acm.address=t.address
                        and t.network = acm.network
                        and cd.network = %s
                        and cd.gs_cluster_id = %s
                        and t.tagpack=tp.id
                        and t.address=cd.address
                        {cluster_definer_condition}
                        and c.id = t.confidence
                        {_private_condition(private, 'cd')}
                   order by
                        cd.max_level desc,
                        cd.no_addresses desc,
                        cd.is_cluster_definer desc,
                        t.address desc
                   limit 1"""  # noqa

        return self._result(
            query,
            [network.upper(), cluster_id],
        )

    def tags_for_entities(self, network, cluster_ids, private):
        c = tuple(i for i in cluster_ids)

        query = f"""select
                acm.gs_cluster_id,
                json_agg(distinct t.label) as labels
               from
                tag t,
                tagpack tp,
                address_cluster_mapping acm
               where
                t.address = acm.address
                and t.network = acm.network
                and t.is_cluster_definer = true
                and acm.network = %s
                and acm.gs_cluster_id in %s
                and tp.id = t.tagpack
                {_private_condition(private, "tp")}
               group by
                acm.gs_cluster_id
               order by acm.gs_cluster_id"""

        return self._result(
            query,
            [network.upper(), c],
        )

    def tags_for_addresses(self, network, addresses, private):
        if network == "eth":
            addresses = tuple(addr.lower().strip() for addr in addresses)
        else:
            addresses = tuple(addr.strip() for addr in addresses)

        query = f"""select
                          t.address,
                          json_agg(distinct t.label) as labels
                         from
                          tag t,
                          tagpack tp
                         where
                          t.tagpack = tp.id
                          and t.network = %s
                          and t.address in %s
                          {_private_condition(private, "tp")}
                         group by address
                         order by address"""

        return self._result(query, [network.upper(), addresses])

    def actors_for_address(self, network, address, show_private=False):

        query = f"""select
                            distinct t.actor as id, ac.label as label
                           from
                            tag t,
                            actor ac,
                            tagpack tp
                           where
                            t.actor = ac.id
                            and t.tagpack = tp.id
                            and t.network = %s
                            and t.address = %s
                            {_private_condition(show_private, "tp")}
                            order by label"""
        return self._result(query, [network.upper(), address])

    def actors_for_entity(self, network, entity, show_private=False):

        query = f"""select
                       distinct t.actor as id, ac.label as label
                      from
                       tag t,
                       actor ac,
                       address_cluster_mapping acm,
                       tagpack tp
                      where
                       t.address = acm.address
                       and t.tagpack = tp.id
                       and t.network = acm.network
                       and acm.network = %s
                       and acm.gs_cluster_id = %s
                       and ac.id = t.actor
                       {_private_condition(show_private, "tp")}
                       order by label"""
        return self._result(
            query,
            [
                network.upper(),
                entity,
            ],
        )

    def get_matching_actors(self, expression, limit, show_private=False):
        query = f"""select
                    a.id,
                    a.label
                   from
                    actor a,
                    actorpack ap
                   where
                    ap.id = a.actorpack
                    and similarity(a.label, %s) > 0.2
                    {_private_condition(show_private, 'ap')}
                   order by a.label <-> %s
                   limit %s"""
        return self._result(query, params=[expression, expression, limit])

    def get_actor(self, id):
        query = "SELECT * FROM actor WHERE id=%s"

        return self._result(query, [id])

    def get_actor_categories(self, id):
        query = (
            "SELECT actor_categories.*,concept.label FROM "
            "actor_categories, concept "
            "WHERE actor_categories.category_id = concept.id and actor_id=%s"
        )

        return self._result(query, [id])

    def get_actor_jurisdictions(self, id):
        query = (
            "SELECT actor_jurisdictions.*,concept.label FROM "
            "actor_jurisdictions, concept "
            "WHERE actor_jurisdictions.country_id = concept.id and actor_id=%s"
        )

        return self._result(query, [id])

    def get_nr_of_tags_by_actor(self, id):
        query = "SELECT count(*) FROM tag WHERE actor=%s"

        return self._result(query, [id])

    def get_tags_for_actor(self, id, show_private=False, page=None, pagesize=None):
        query = f"""select
                        t.*,
                        tp.uri,
                        tp.creator,
                        tp.title,
                        tp.is_public,
                        c.level,
                        acm.gs_cluster_id
                    from
                       tag t,
                       tagpack tp,
                       confidence c,
                       address_cluster_mapping acm
                   where
                       t.tagpack = tp.id
                       and t.confidence = c.id
                       and acm.address=t.address
                       and acm.network=t.network
                       {_private_condition(show_private, "tp")}
                       and t.actor = %s """

        return self._result(
            query,
            [id],
            page,
            pagesize,
        )

    def low_quality_address_labels(self, th=0.25, network="", category="") -> dict:
        """
        This function returns a list of addresses having a quality meassure
        equal or lower than a threshold value, along with the corresponding
        tags for each address.
        """
        validate_network(network)
        network = network if network else "%"
        category = category if category else "%"

        msg = "Threshold must be a float number between 0 and 1"
        try:
            th = float(th)
            if th < 0 or th > 1:
                raise ValidationError(msg)
        except ValueError:
            raise ValidationError(msg)

        q = "SELECT j.network, j.address, array_agg(j.label) labels \
            FROM ( \
                SELECT q.network, q.address, t.label \
                FROM address_quality q, tag t \
                WHERE t.category ILIKE %s \
                    AND t.address=q.address \
                    AND q.network LIKE %s \
                    AND q.quality <= %s \
            ) as j \
            GROUP BY j.network, j.address"

        self.cursor.execute(
            q,
            (
                category,
                network,
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
                            t.actor,
                            t.is_cluster_definer,
                            t.category,
                            t.currency,
                            t.network,
                            t.confidence,
                            t.abuse,
                            tp.creator,
                            ROW_NUMBER() OVER (PARTITION BY t.address,
                                t.label,
                                t.source,
                                t.actor,
                                t.is_cluster_definer,
                                t.category,
                                t.currency,
                                t.network,
                                t.confidence,
                                t.abuse,
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

    @auto_commit
    def refresh_db(self):
        self.cursor.execute("REFRESH MATERIALIZED VIEW label")
        self.cursor.execute("REFRESH MATERIALIZED VIEW statistics")
        self.cursor.execute("REFRESH MATERIALIZED VIEW tag_count_by_cluster")
        self.cursor.execute(
            "REFRESH MATERIALIZED VIEW "
            "cluster_defining_tags_by_frequency_and_maxconfidence"
        )  # noqa

    def get_addresses(self, update_existing):
        if update_existing:
            self.cursor.execute("SELECT address, network FROM address")
        else:
            q = "SELECT address, network FROM address WHERE NOT is_mapped"
            self.cursor.execute(q)
        for record in self.cursor:
            yield record

    def get_tagstore_composition(self, by_network=False):
        if by_network:
            self.cursor.execute(
                "SELECT creator, "
                "category, "
                "tp.is_public as is_public, "
                "t.network as network, "
                "count(distinct t.label) as labels_count, "
                "count(*) as tags_count "
                "FROM tag t, tagpack tp where t.tagpack = tp.id "
                "group by network, creator, category, is_public;"
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

    @auto_commit
    def insert_cluster_mappings(self, clusters):
        if not clusters.empty:
            q = "INSERT INTO address_cluster_mapping (address, network, \
                gs_cluster_id , gs_cluster_def_addr , gs_cluster_no_addr) \
                VALUES (%s, %s, %s, %s, %s) ON CONFLICT (network, address) \
                DO UPDATE SET gs_cluster_id = EXCLUDED.gs_cluster_id, \
                gs_cluster_def_addr = EXCLUDED.gs_cluster_def_addr, \
                gs_cluster_no_addr = EXCLUDED.gs_cluster_no_addr"

            cols = [
                "address",
                "network",
                "cluster_id",
                "cluster_defining_address",
                "no_addresses",
            ]
            data = clusters[cols].to_records(index=False)

            execute_batch(self.cursor, q, data)

    @auto_commit
    def finish_mappings_update(self, keys):
        q = "UPDATE address SET is_mapped=true WHERE NOT is_mapped \
                AND network IN %s"
        self.cursor.execute(q, (tuple(keys),))

    def get_ingested_tagpacks(self) -> List:
        self.cursor.execute("SELECT id from tagpack")
        return [i[0] for i in self.cursor.fetchall()]

    def get_tags_count(self, network="") -> int:
        validate_network(network)

        if network:
            self.cursor.execute("SELECT count(*) FROM tag where network=%s", (network,))
        else:
            self.cursor.execute("SELECT count(*) FROM tag")

        return self.cursor.fetchall()[0][0]

    def get_tags_with_actors_count(self, network="") -> int:
        validate_network(network)

        if network:
            self.cursor.execute(
                "SELECT count(*) FROM tag where actor is not NULL and network=%s",
                (network,),
            )
        else:
            self.cursor.execute("SELECT count(*) FROM tag where actor is not NULL")

        return self.cursor.fetchall()[0][0]

    def get_used_actors_count(self, network="", category="") -> int:
        validate_network(network)

        params = {"network": network}
        cat_join, cat_filter, network_filter = ("", "", "")

        if network:
            network_filter = "AND network=%(network)s"

        if len(category) > 0:
            cat_join = (
                "INNER JOIN actor_categories "
                "on tag.actor = actor_categories.actor_id"
            )
            cat_filter = "AND actor_categories.category_id = %(category)s"
            params["category"] = category.strip()

        query = (
            "SELECT count(DISTINCT actor) FROM tag "
            f"{cat_join} "
            "WHERE actor is not NULL "
            f"{network_filter} "
            f"{cat_filter} "
        )
        self.cursor.execute(query, params)

        return self.cursor.fetchall()[0][0]

    def get_used_actors_with_jurisdictions(self, network="", category="") -> int:
        validate_network(network)
        params = {"network": network}
        cat_join, cat_filter, network_filter = ("", "", "")

        if network:
            network_filter = "AND network=%(network)s"

        if len(category) > 0:
            cat_join = (
                "INNER JOIN actor_categories "
                "on tag.actor = actor_categories.actor_id"
            )
            cat_filter = "AND actor_categories.category_id = %(category)s"
            params["category"] = category.strip()

        query = (
            "SELECT count(DISTINCT actor) FROM tag "
            "INNER JOIN actor_jurisdictions "
            "on tag.actor = actor_jurisdictions.actor_id "
            f"{cat_join} "
            "WHERE actor is not NULL "
            f"{network_filter} "
            f"{cat_filter} "
        )

        self.cursor.execute(query, params)

        return self.cursor.fetchall()[0][0]

    def get_quality_measures(self, network="") -> dict:
        """
        This function returns a dict with the quality measures (count, avg, and
        stddev) for a specific network, or for all if networks is not
        specified.
        """
        validate_network(network)

        query = "SELECT COUNT(quality), AVG(quality), STDDEV(quality)"
        query += " FROM address_quality"
        if network:
            query += " WHERE network=%s"
            self.cursor.execute(query, (network,))
        else:
            self.cursor.execute(query)

        keys = ["count", "avg", "stddev"]
        ret = {keys[i]: v for row in self.cursor.fetchall() for i, v in enumerate(row)}

        ret["tag_count"] = self.get_tags_count(network=network)
        ret["tag_count_with_actors"] = self.get_tags_with_actors_count(network=network)
        ret["nr_actors_used"] = self.get_used_actors_count(network=network)
        ret[
            "nr_actors_used_with_jurisdictions"
        ] = self.get_used_actors_with_jurisdictions(network=network)

        ret["nr_actors_used_exchange"] = self.get_used_actors_count(
            network=network, category="exchange"
        )
        ret[
            "nr_actors_used_with_jurisdictions_exchange"
        ] = self.get_used_actors_with_jurisdictions(
            network=network, category="exchange"
        )

        return ret

    def calculate_quality_measures(self) -> dict:
        self.cursor.execute("CALL calculate_quality(FALSE)")
        self.cursor.execute("CALL insert_address_quality()")
        self.conn.commit()
        return self.get_quality_measures()

    def list_tags(self, unique=False, category="", network=""):
        validate_network(network)
        network = network if network else "%"
        category = category if category else "%"

        q = (
            f"SELECT {'DISTINCT' if unique else ''} "
            "t.network, tp.title, t.label "
            "FROM tagpack tp, tag t WHERE t.tagpack = tp.id "
            "AND t.category ILIKE %s AND t.network LIKE %s "
            "ORDER BY t.network, tp.title, t.label ASC"
        )
        v = (category, network)
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

    def list_address_actors(self, network=""):
        validate_network(network)
        network = network if network else "%"
        q = (
            "SELECT t.id, t.label, t.address, t.category, a.label "
            "FROM tag t, actor a "
            "WHERE t.label = a.id "
            "AND t.network LIKE %s"
        )
        v = (network,)
        self.cursor.execute(q, v)
        return self.cursor.fetchall()


def validate_network(network):
    network = network.upper()
    if network not in ([""] + list(KNOWN_NETWORKS.keys())):
        print_warn(f"WARNING: Unknown network {network}")


def _get_tag_concepts(tag):
    return tag.all_fields.get("concepts", [])


def _get_tag(tag, tagpack_id):
    label = tag.all_fields.get("label").lower().strip()
    lastmod = tag.all_fields.get("lastmod", datetime.now().isoformat())

    _, address = _get_network_and_address(tag)

    return (
        label,
        tag.all_fields.get("source"),
        tag.all_fields.get("category", None),
        tag.all_fields.get("abuse", None),
        address,
        tag.all_fields.get("currency").upper(),
        tag.all_fields.get("network").upper(),
        tag.all_fields.get("is_cluster_definer"),
        tag.all_fields.get("confidence"),
        lastmod,
        tag.all_fields.get("context"),
        tagpack_id,
        tag.all_fields.get("actor", None),
    )


def _perform_address_modifications(address, network):
    if "BCH" == network.upper() and address.startswith("bitcoincash"):
        address = to_legacy_address(address)

    elif "ETH" == network.upper():
        address = address.lower()

    return address


def _get_network_and_address(tag):
    net = tag.all_fields.get("network").upper()
    addr = tag.all_fields.get("address")

    addr = _perform_address_modifications(addr, net)

    return net, addr


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
    return {
        "id": actor.all_fields.get("id"),
        "label": actor.all_fields.get("label", "").strip(),
        "context": context.strip() if context is not None else context,
        "uri": uri.strip() if uri is not None else uri,
        "lastmod": actor.all_fields.get("lastmod", datetime.now().isoformat()),
        "actorpack": actorpack_id,
    }


def _get_actor_categories(actor):
    data = []
    actor_id = actor.all_fields.get("id")
    for category in actor.all_fields.get("categories"):
        data.append({"actor_id": actor_id, "category_id": category})
    return data


def _get_actor_jurisdictions(actor):
    data = []
    actor_id = actor.all_fields.get("id")
    if "jurisdictions" in actor.all_fields:
        for country in actor.all_fields.get("jurisdictions"):
            data.append({"actor_id": actor_id, "country_id": country})
    return data
