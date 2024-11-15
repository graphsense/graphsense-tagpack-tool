CREATE TABLE taxonomy (
    id                  VARCHAR     PRIMARY KEY,
    source              VARCHAR     NOT NULL,
    description         VARCHAR     DEFAULT NULL
);

CREATE TABLE concept (
    id                  VARCHAR     PRIMARY KEY,
    label               VARCHAR     NOT NULL,
    source              VARCHAR     NOT NULL,
    description         VARCHAR     NOT NULL,
    taxonomy            VARCHAR     NOT NULL REFERENCES taxonomy(id) ON DELETE CASCADE
);

CREATE TABLE tag_type (
    id                  VARCHAR     PRIMARY KEY,
    label               VARCHAR     NOT NULL,
    source              VARCHAR     NOT NULL,
    description         VARCHAR     NOT NULL,
    taxonomy            VARCHAR     NOT NULL REFERENCES taxonomy(id) ON DELETE CASCADE
);

CREATE TABLE country (
    id                  VARCHAR     PRIMARY KEY,
    label               VARCHAR     NOT NULL,
    source              VARCHAR     NOT NULL,
    description         VARCHAR     NOT NULL,
    taxonomy            VARCHAR     NOT NULL REFERENCES taxonomy(id) ON DELETE CASCADE
);


CREATE TABLE tag_subject (
    id                  VARCHAR     PRIMARY KEY,
    label               VARCHAR     NOT NULL,
    source              VARCHAR     NOT NULL,
    description         VARCHAR     NOT NULL,
    taxonomy            VARCHAR     NOT NULL REFERENCES taxonomy(id) ON DELETE CASCADE
);


-- Pre-defined confidence levels

CREATE TABLE confidence (
    id                  VARCHAR     PRIMARY KEY,
    label               VARCHAR     NOT NULL,
    description         VARCHAR     NOT NULL,
    level               INTEGER     NOT NULL
);


-- Actor and ActorPack tables

CREATE TABLE actorpack (
    id                  VARCHAR     PRIMARY KEY,
    title               VARCHAR     NOT NULL,
    creator             VARCHAR     NOT NULL,
    description         VARCHAR     NOT NULL,
    uri                 VARCHAR     ,
    lastmod             TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE actor (
    id                  VARCHAR     PRIMARY KEY,
    uri                 VARCHAR     ,
    label               VARCHAR     NOT NULL,
    context             VARCHAR     DEFAULT NULL,
    lastmod             TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actorpack           VARCHAR     REFERENCES actorpack(id) ON DELETE CASCADE,
    CONSTRAINT unique_actor UNIQUE (id)
);


CREATE TABLE tagpack (
    id                  VARCHAR     PRIMARY KEY,
    title               VARCHAR     NOT NULL,
    description         VARCHAR     NOT NULL,
    creator             VARCHAR     NOT NULL,
    uri                 VARCHAR     ,
    acl_group           VARCHAR     NOT NULL DEFAULT 'public',
    lastmod             TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE tag (
    id                  SERIAL      PRIMARY KEY,
    label               VARCHAR     NOT NULL,
    source              VARCHAR     DEFAULT NULL,
    context             VARCHAR     DEFAULT NULL,
    is_cluster_definer  BOOLEAN     DEFAULT FALSE,
    lastmod             TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    identifier          VARCHAR     NOT NULL,
    asset               VARCHAR     NOT NULL,
    network             VARCHAR     NOT NULL,
    confidence          VARCHAR     REFERENCES confidence(id),
    tag_type            VARCHAR     REFERENCES tag_type(id) NOT NULL,
    tag_subject         VARCHAR     REFERENCES tag_subject(id) NOT NULL,
    tagpack             VARCHAR     REFERENCES tagpack(id) ON DELETE CASCADE,
    actor               VARCHAR     REFERENCES actor(id),
    CONSTRAINT unique_tag UNIQUE (identifier, network, tagpack, label, source)
);

CREATE TABLE address (
    network             VARCHAR    NOT NULL,
    address             VARCHAR     NOT NULL,
    created             TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_mapped           BOOLEAN     NOT NULL DEFAULT FALSE,
    -- FOREIGN KEY (network, address) REFERENCES tag (network, identifier),
    PRIMARY KEY (network, address)
);

-- CREATE INDEX curr_network_index ON address (network, address);

CREATE TABLE actor_concept (
    actor_id            VARCHAR     REFERENCES actor(id) ON DELETE CASCADE,
    category_id         VARCHAR     REFERENCES concept(id) ON DELETE CASCADE,
    CONSTRAINT unique_category UNIQUE (actor_id, category_id),
    PRIMARY KEY (actor_id, category_id)
);

CREATE TABLE actor_jurisdiction (
    actor_id            VARCHAR     REFERENCES actor(id) ON DELETE CASCADE,
    country_id          VARCHAR     REFERENCES country(id) ON DELETE CASCADE,
    CONSTRAINT unique_jurisdiction UNIQUE (actor_id, country_id),
    PRIMARY KEY (actor_id, country_id)
);

CREATE TABLE tag_concept (
    tag_id              INTEGER     REFERENCES tag(id) ON DELETE CASCADE,
    concept_type        VARCHAR     DEFAULT NULL,
    concept_id          VARCHAR     REFERENCES concept(id) ON DELETE CASCADE,
    CONSTRAINT unique_concept UNIQUE (tag_id, concept_id),
    PRIMARY KEY (tag_id, concept_id)
);


CREATE INDEX tag_label_index ON tag (label);
CREATE INDEX tag_ident_index ON tag (identifier);
CREATE INDEX tag_is_cluster_definer_index ON tag (is_cluster_definer);

-- GraphSense mapping table

CREATE TABLE address_cluster_mapping (
    address             VARCHAR     NOT NULL,
    network               VARCHAR    NOT NULL,
    gs_cluster_id       INTEGER     NOT NULL,
    gs_cluster_def_addr VARCHAR     NOT NULL,
    gs_cluster_no_addr  INTEGER     DEFAULT NULL,
    PRIMARY KEY(network, address),
    FOREIGN KEY (network, address) REFERENCES address (network, address) ON DELETE CASCADE
);
CREATE INDEX acm_gs_cluster_id_index ON address_cluster_mapping (network, gs_cluster_id);


-- setup fuzzy search resources
DROP EXTENSION IF EXISTS fuzzystrmatch;
DROP EXTENSION IF EXISTS pg_trgm;

CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

CREATE MATERIALIZED VIEW label AS SELECT DISTINCT label FROM tag;

-- -- TODO: add triggers updating lastmod on update

CREATE MATERIALIZED VIEW statistics AS
    SELECT
        explicit.network,
        no_labels,
        explicit.no_tagged_addresses as no_explicit_tagged_addresses,
        COALESCE(implicit.no_tagged_addresses, explicit.no_tagged_addresses) as no_implicit_tagged_addresses
    FROM
        (SELECT
            network,
            NULL,
            COUNT(DISTINCT label) AS no_labels,
            COUNT(DISTINCT identifier) AS no_tagged_addresses
         FROM
            tag
         GROUP BY
            network
        ) explicit
    LEFT JOIN
        (SELECT
            SUM(gs_cluster_no_addr) AS no_tagged_addresses,
            network
         FROM
            (SELECT DISTINCT ON (gs_cluster_id, network)
                network,
                gs_cluster_no_addr
             FROM address_cluster_mapping
            ) t
         GROUP
            BY network
        ) implicit
    ON implicit.network = explicit.network;

CREATE MATERIALIZED VIEW tag_count_by_cluster AS
    SELECT
        t.network,
        acm.gs_cluster_id,
        tp.acl_group,
        count(t.identifier) as count
    FROM
        tag t,
        tagpack tp,
        address_cluster_mapping acm
    WHERE
        acm.address=t.identifier
        AND acm.network=t.network
        AND t.tagpack=tp.id
    GROUP BY
        t.network,
        acm.gs_cluster_id,
        tp.acl_group;

CREATE INDEX tag_count_curr_cluster_index ON tag_count_by_cluster (network, gs_cluster_id);

/* In the end this view fulfils the following requirements in junction with
 * REST's `list_entity_tags_by_entity`:
 *  If there is no address tag with is_cluster_definer = True -> no cluster tag
 *  If there is an address tag with is_cluster_definer = True -> assign on cluster level
 *  If there are several address tags with is_cluster_definer = True -> take the one with higher confidence value
 *  If there are several address tags with is_cluster_definer = True and same confidence value and if the labels are the same -> take one of them and assign it to cluster level
 *  If cluster size = 1 and there is an address tag on that single address -> assign to cluster level
 *  If cluster size = 1 and there are several address tags on that single address -> assign the one with highest confidence
 */
CREATE MATERIALIZED VIEW cluster_defining_tags_by_frequency_and_maxconfidence AS
    SELECT
        acm.gs_cluster_id,
        t.network,
        t.label,
        -- t.category,
        tp.acl_group,
        MIN(t.identifier) as address,
        COUNT(t.identifier) AS no_addresses,
        c.level AS max_level,
        true AS is_cluster_definer
    FROM
        tag t,
        address_cluster_mapping acm,
        confidence c,
        tagpack tp
    WHERE
        acm.address=t.identifier
        AND acm.network=t.network
        AND t.is_cluster_definer=true
        AND t.confidence=c.id
        AND tp.id=t.tagpack
    GROUP BY
        c.level,
        t.label,
        -- t.category,
        t.network,
        acm.gs_cluster_id,
        tp.acl_group
    UNION
        SELECT
            gs_cluster_id,
            t.network,
            t.label,
            -- t.category,
            -- string_agg(tp.acl_group,'|') AS acl_group,
            tp.acl_group,
            MIN(t.identifier) as address,
            1 AS no_addresses,
            MAX(c.level) AS max_level,
            false AS is_cluster_definer
        FROM
            address_cluster_mapping acm,
            tag t,
            confidence c,
            tagpack tp
        WHERE
            c.id=t.confidence
            and tp.id=t.tagpack
            and t.identifier=acm.address
            and t.network=acm.network
            and acm.gs_cluster_no_addr = 1
        GROUP BY
            t.label,
            -- t.category,
            t.network,
            acm.gs_cluster_id,
            tp.acl_group
        HAVING
            every(t.is_cluster_definer=false or t.is_cluster_definer is null);

CREATE INDEX cluster_tags_gs_cluster_index ON cluster_defining_tags_by_frequency_and_maxconfidence (network, gs_cluster_id);

-- -- Tag quality helper views

-- -- CREATE VIEW duplicate_tags AS
-- --     SELECT
-- --         t.address,
-- --         t.label,
-- --         t.source,
-- --         tp.creator,
-- --         COUNT(*)
-- --     FROM
-- --         tag t,
-- --         tagpack tp
-- --     WHERE
-- --         t.tagpack = tp.id
-- --     GROUP BY
-- --         t.address,
-- --         t.label,
-- --         t.source,
-- --         tp.creator
-- --     HAVING
-- --         COUNT(*) > 1
-- --     ORDER BY
-- --         count DESC;

-- Quality measures

DROP TABLE IF EXISTS address_quality;
CREATE TABLE IF NOT EXISTS address_quality(
	id SERIAL PRIMARY KEY,
	network VARCHAR,
	identifier VARCHAR,
	n_tags INTEGER,
	n_dif_tags INTEGER,
	total_pairs INTEGER,
	q1 INTEGER,
	q2 INTEGER,
	q3 INTEGER,
	q4 INTEGER,
	quality NUMERIC
);

-- Procedure to calculate the quality measures, usage: CALL calculate_quality();

CREATE PROCEDURE calculate_quality(actor BOOLEAN DEFAULT FALSE)
LANGUAGE PLPGSQL
AS $$
DECLARE
	i RECORD;
	e RECORD;
	s RECORD;
	sim NUMERIC;
	_tag_column TEXT;
BEGIN
	DROP TABLE IF EXISTS quality_pairs;
	CREATE TEMP TABLE IF NOT EXISTS quality_pairs(
		id SERIAL PRIMARY KEY,
		network VARCHAR,
		identifier VARCHAR,
		label1 VARCHAR,
		label2 VARCHAR,
		sim NUMERIC
	);
	DROP TABLE IF EXISTS quality_labels;
	CREATE TEMP TABLE IF NOT EXISTS quality_labels(
		id SERIAL PRIMARY KEY,
		network VARCHAR,
		identifier VARCHAR,
		label VARCHAR,
		label_id INTEGER
	);
	IF actor THEN _tag_column='actor'; ELSE _tag_column='label'; END IF;
	FOR i in EXECUTE ( format(
		'SELECT t.network, t.identifier, COUNT(DISTINCT t.%1$I) n_labels
		FROM tag t
		GROUP BY network, identifier
		HAVING COUNT(DISTINCT t.%1$I) > 1'
		, _tag_column
	))
	LOOP
		FOR e in SELECT * FROM tag WHERE network=i.network AND identifier=i.identifier LOOP
			-- RAISE NOTICE '%:%', e.identifier, e.label;
			FOR s in SELECT u.label label, similarity(u.label, e.label) simi FROM quality_labels u WHERE u.identifier = e.identifier LOOP
				-- RAISE NOTICE '% <-> % = %', e.label, s.label, s.simi;
				sim = s.simi;
				INSERT INTO quality_pairs (network, identifier, label1, label2, sim)
				VALUES (e.network, e.identifier, e.label, s.label, sim);
			END LOOP;
		        INSERT INTO quality_labels (network, identifier, label, label_id)
		        VALUES (e.network, e.identifier, e.label, e.id);
		END LOOP;
	END LOOP;
END $$;

-- Save quality measures into address_quality table

CREATE PROCEDURE insert_address_quality()
LANGUAGE PLPGSQL
AS $$
BEGIN
TRUNCATE address_quality;
INSERT INTO address_quality
	(network, identifier, n_tags, n_dif_tags, total_pairs, q1, q2, q3, q4, quality)
SELECT
	tags.network, tags.identifier, tags.n_tags, tags.n_dif_tags,
	pairs.total total_pairs, sim.q1, sim.q2, sim.q3, sim.q4,
	1-((sim.q1*0.25+sim.q2*0.5+sim.q3*0.75+sim.q4*1.0)/pairs.total::float) quality
FROM (
	SELECT
		t.network, t.identifier, COUNT(t.label) n_tags, COUNT(DISTINCT(t.label)) n_dif_tags
	FROM tag t
	GROUP BY t.network, t.identifier
	HAVING COUNT(DISTINCT(t.label)) > 1
) tags
LEFT OUTER JOIN (
	SELECT
		q.network, q.identifier, COUNT(q.sim) n_sim
	FROM quality_pairs q
	WHERE q.sim <= 0.25
	GROUP BY q.network, q.identifier
) quality_q1
ON tags.network = quality_q1.network AND tags.identifier = quality_q1.identifier
LEFT OUTER JOIN (
	SELECT
		q.network, q.identifier, COUNT(q.sim) n_sim
	FROM quality_pairs q
	WHERE q.sim > 0.25 AND q.sim <= 0.5
	GROUP BY q.network, q.identifier
) quality_q2
ON tags.network = quality_q2.network AND tags.identifier = quality_q2.identifier
LEFT OUTER JOIN (
	SELECT
		q.network, q.identifier, COUNT(q.sim) n_sim
	FROM quality_pairs q
	WHERE q.sim > 0.50 AND q.sim <= 0.75
	GROUP BY q.network, q.identifier
) quality_q3
ON tags.network = quality_q3.network AND tags.identifier = quality_q3.identifier
LEFT OUTER JOIN (
	SELECT
		q.network, q.identifier, COUNT(q.sim) n_sim
	FROM quality_pairs q
	WHERE q.sim > 0.75
	GROUP BY q.network, q.identifier
) quality_q4
ON tags.network = quality_q4.network AND tags.identifier = quality_q4.identifier
CROSS JOIN LATERAL (
	SELECT
		coalesce(quality_q1.n_sim, 0),
		coalesce(quality_q2.n_sim, 0),
		coalesce(quality_q3.n_sim, 0),
		coalesce(quality_q4.n_sim, 0)
) as sim(q1, q2, q3, q4)
CROSS JOIN LATERAL (
	SELECT
		(sim.q1+sim.q2+sim.q3+sim.q4)
) as pairs(total);
END $$;
