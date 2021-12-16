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
    id                  SERIAL      PRIMARY KEY,
	level				INTEGER		NOT NULL,
	label 				VARCHAR		NOT NULL,
	description			VARCHAR		NOT NULL,
	examples			VARCHAR		DEFAULT NULL
);

INSERT INTO confidence (level, label, description)
	VALUES(100, 'Proven ownership', 'Known private key owner for a given address');
INSERT INTO confidence (level, label, description)
	VALUES(90, 'Manual transaction', 'Self-executed transaction and known involved entities');
INSERT INTO confidence (level, label, description, examples)
	VALUES(80, 'Service API', 'Data retrieved from API of a known service', 'Bitpanda API');
INSERT INTO confidence (level, label, description, examples)
	VALUES(60, 'Authority data', 'Data retrieved from public authorities', 'OFAC');
INSERT INTO confidence (level, label, description, examples)
	VALUES(50, 'Trusted data providers', 'Data retrieved from trusted third parties', 'Darknet crawl, Spam trap');
INSERT INTO confidence (level, label, description, examples)
	VALUES(50, 'Service data', 'Data retrieved from a known service', 'CSV file received from exchange');
INSERT INTO confidence (level, label, description, examples)
	VALUES(50, 'Forensic reports', 'Data retrieved from somehow trusted reports', 'Academic papers');
INSERT INTO confidence (level, label, description)
	VALUES(40, 'Untrusted transaction', 'Transaction executed by third parties');
INSERT INTO confidence (level, label, description)
	VALUES(20, 'Web Crawls', 'Data retrieved from Web of data dump crawls');

-- Tag & TagPack tables

CREATE TABLE address (
    currency			VARCHAR		,
	address				VARCHAR		,
	created				TIMESTAMP 	NOT NULL DEFAULT CURRENT_TIMESTAMP,
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
	currency		    VARCHAR		NOT NULL,
	confidence			INTEGER		, --REFERENCES confidence(id),
	abuse				VARCHAR		REFERENCES concept(id),
	category			VARCHAR		REFERENCES concept(id),
	tagpack				VARCHAR		REFERENCES tagpack(id) ON DELETE CASCADE,
	FOREIGN KEY (currency, address) REFERENCES address (currency, address)
);

CREATE INDEX tag_label_index ON tag (label);
CREATE INDEX tag_address_index ON tag (address);
CREATE INDEX tag_is_cluster_definer_index ON tag (is_cluster_definer);

-- GraphSense mapping table

CREATE TABLE address_cluster_mapping (
	address 			VARCHAR		NOT NULL,
	currency            VARCHAR     NOT NULL,
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
CREATE EXTENSION fuzzystrmatch;
CREATE EXTENSION pg_trgm;

CREATE MATERIALIZED VIEW label AS SELECT DISTINCT label FROM tag;

-- TODO: add triggers updating lastmod on update


