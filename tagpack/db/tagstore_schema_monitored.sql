-- Monitoring 
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- CREATE EXTENSION IF NOT EXISTS plpython3u;

-- Actual db stuff
DROP SCHEMA IF EXISTS tagstore;

CREATE SCHEMA tagstore;

SET search_path to tagstore;


-- Taxonomy & Concept Tables

CREATE TABLE taxonomy (
	id 				    VARCHAR 	PRIMARY KEY,
	source 				VARCHAR		NOT NULL,
	description			VARCHAR		DEFAULT NULL
);

CREATE TABLE concept (
	id 					VARCHAR 	PRIMARY KEY,
	label 				VARCHAR 	NOT NULL,
	source 				VARCHAR		NOT NULL,
	description			VARCHAR		NOT NULL,
	taxonomy			VARCHAR		NOT NULL REFERENCES taxonomy(id) ON DELETE CASCADE
);

-- Agreed-upon Confidence Levels
-- see https://github.com/graphsense/graphsense-tagpacks/blob/master/README.md#attribution-tag-confidence-score

CREATE TABLE confidence (
    id                  VARCHAR      PRIMARY KEY,
	label 				VARCHAR		NOT NULL,
	description			VARCHAR		NOT NULL,
	level				INTEGER		NOT NULL
);


INSERT INTO confidence (id, label, description, level)
	VALUES('override', 'Manual cluster tag', 'Creator knows that a tag is representative for an entire cluster and overrides all other tags', 100);
INSERT INTO confidence (id, label, description, level)
	VALUES('ownership', 'Proven address ownership', 'Creator controls the private key the address associated with a tag', 100);
INSERT INTO confidence (id, label, description, level)
	VALUES('manual_transaction', 'Trusted transaction', 'Creator transferred funds from known service x to known service y', 90);
INSERT INTO confidence (id, label, description, level)
	VALUES('service_api', 'Service API', 'Creator retrieves addresses from a known and trusted service provider API (e.g. VASP API)', 70);
INSERT INTO confidence (id, label, description, level)
	VALUES('authority_data', 'Authority data', 'Creator retrieves attribution tags from public authorities (e.g. OFAC)', 60);
INSERT INTO confidence (id, label, description, level)
	VALUES('trusted_provider', 'Trusted data providers', 'Creator retrieved attribution tags from trusted third parties (e.g. spam trap)', 50);
INSERT INTO confidence (id, label, description, level)
	VALUES('service_data', 'Service data', 'Creator retrieved attribution tag from a known service (e.g. CSV file received from exchange)', 50);
INSERT INTO confidence (id, label, description, level)
	VALUES('forensic', 'Forensic reports', 'Creator retrieved data attribution data from somehow trusted reports (e.g. academic papers)', 50);
INSERT INTO confidence (id, label, description, level)
	VALUES('untrusted_transaction', 'Untrusted transaction', 'A third party transferred funds from known service x to known service y', 40);
INSERT INTO confidence (id, label, description, level)
	VALUES('web_crawl', 'Web crawls', 'Attribution tags were retrieved from crawling the web or other data dumps', 20);


-- supported currencies

CREATE TYPE currency AS ENUM ('BCH', 'BTC', 'ETH', 'LTC', 'ZEC');


-- Tag & TagPack tables

CREATE TABLE address (
    currency			currency	NOT NULL,
	address				VARCHAR		NOT NULL,
	created				TIMESTAMP 	NOT NULL DEFAULT CURRENT_TIMESTAMP,
	is_mapped           BOOLEAN     NOT NULL DEFAULT FALSE,
	PRIMARY KEY(currency, address)
);

CREATE INDEX curr_addr_index ON address (currency, address);

CREATE TABLE tagpack (
	id				    VARCHAR		PRIMARY KEY,
	title               VARCHAR     NOT NULL,
	description			VARCHAR		NOT NULL,
	source 				VARCHAR		DEFAULT NULL,
	creator				VARCHAR		NOT NULL,
	owner				VARCHAR		NOT NULL,
	uri                 VARCHAR     ,
	is_public			BOOLEAN		DEFAULT FALSE,
	lastmod				TIMESTAMP 	NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE tag (
	id 					SERIAL 		PRIMARY KEY,
	label 				VARCHAR 	NOT NULL,
	source				VARCHAR		DEFAULT NULL,
	context				VARCHAR		DEFAULT NULL,
	is_cluster_definer	BOOLEAN		DEFAULT NULL,
	lastmod				TIMESTAMP	NOT NULL DEFAULT CURRENT_TIMESTAMP,
	address				VARCHAR		NOT NULL,
	currency		    currency    NOT NULL,
	confidence			VARCHAR		REFERENCES confidence(id),
	abuse				VARCHAR		REFERENCES concept(id),
	category			VARCHAR		REFERENCES concept(id),
	tagpack				VARCHAR		REFERENCES tagpack(id) ON DELETE CASCADE,
	FOREIGN KEY (currency, address) REFERENCES address (currency, address),
	CONSTRAINT unique_tag UNIQUE (address, currency, tagpack, label, source)
);

CREATE INDEX tag_label_index ON tag (label);
CREATE INDEX tag_address_index ON tag (address);
CREATE INDEX tag_is_cluster_definer_index ON tag (is_cluster_definer);

-- GraphSense mapping table

CREATE TABLE address_cluster_mapping (
	address 			VARCHAR		NOT NULL,
	currency            currency    NOT NULL,
	gs_cluster_id 		INTEGER		NOT NULL,
	gs_cluster_def_addr	VARCHAR		NOT NULL,
	gs_cluster_no_addr	INTEGER		DEFAULT NULL,
	gs_cluster_in_degr	INTEGER		DEFAULT NULL,
	gs_cluster_out_degr INTEGER		DEFAULT NULL,
	PRIMARY KEY(currency, address),
	FOREIGN KEY (currency, address) REFERENCES address (currency, address) ON DELETE CASCADE
);

CREATE INDEX acm_gs_cluster_id_index ON address_cluster_mapping (gs_cluster_id);


-- setup fuzzy search resources
DROP EXTENSION IF EXISTS fuzzystrmatch;
DROP EXTENSION IF EXISTS pg_trgm;

CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE MATERIALIZED VIEW label AS SELECT DISTINCT label FROM tag;

-- TODO: add triggers updating lastmod on update

CREATE MATERIALIZED VIEW statistics AS 
    SELECT 
        explicit.currency,
        no_labels,
        explicit.no_tagged_addresses as no_explicit_tagged_addresses,
        COALESCE(implicit.no_tagged_addresses, explicit.no_tagged_addresses) as no_implicit_tagged_addresses
    FROM
        (SELECT 
            currency,
            NULL,
            COUNT(DISTINCT label) AS no_labels,
            COUNT(DISTINCT address) AS no_tagged_addresses
         FROM 
            tag
         GROUP BY 
            currency
        ) explicit
    LEFT JOIN
        (SELECT 
            SUM(gs_cluster_no_addr) AS no_tagged_addresses,
            currency
         FROM
            (SELECT DISTINCT ON (gs_cluster_id, currency) 
                currency,
                gs_cluster_no_addr
             FROM address_cluster_mapping
            ) t 
         GROUP
            BY currency
        ) implicit 
    ON implicit.currency = explicit.currency
