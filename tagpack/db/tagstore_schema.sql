DROP TABLE IF EXISTS tag;
DROP TABLE IF EXISTS confidence;
DROP TABLE IF EXISTS concept;
DROP TABLE IF EXISTS taxonomy;
DROP TABLE IF EXISTS tagpack;
DROP TABLE IF EXISTS address_cluster_mapping;
DROP TABLE IF EXISTS address;

-- Taxonomy & Concept Tables

CREATE TABLE taxonomy (
	id 					SERIAL 		PRIMARY KEY,
	label 				VARCHAR 	NOT NULL,
	source 				VARCHAR		DEFAULT NULL,
	description			VARCHAR		NOT NULL
);

CREATE TABLE concept (
	id 					VARCHAR 	PRIMARY KEY,
	label 				VARCHAR 	NOT NULL,
	source 				VARCHAR		DEFAULT NULL,
	description			VARCHAR		NOT NULL,
	taxonomy			INTEGER		REFERENCES taxonomy(id) ON DELETE CASCADE
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
	id 					SERIAL		PRIMARY KEY,
	currency			VARCHAR		NOT NULL,
	address				VARCHAR		NOT NULL,
	created				TIMESTAMP 	NOT NULL DEFAULT CURRENT_TIMESTAMP,
	UNIQUE(currency, address)
);

CREATE INDEX curr_addr_index ON address (currency, address);

CREATE TABLE tagpack (
	id 					SERIAL 		PRIMARY KEY,
	title				VARCHAR		NOT NULL,
	description			VARCHAR		NOT NULL,
	source 				VARCHAR		DEFAULT NULL,
	creator				VARCHAR		NOT NULL,
	owner				VARCHAR		NOT NULL,
	is_public			BOOLEAN		DEFAULT FALSE,
	created				TIMESTAMP 	NOT NULL DEFAULT CURRENT_TIMESTAMP,
	lastmod				TIMESTAMP 	NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE tag (
	id 					SERIAL 		PRIMARY KEY,
	label 				VARCHAR 	NOT NULL,
	source				VARCHAR		DEFAULT NULL,
	context				VARCHAR		DEFAULT NULL,
	is_cluster_definer	BOOLEAN		DEFAULT NULL,
	created				TIMESTAMP	NOT NULL DEFAULT CURRENT_TIMESTAMP,
	lastmod				TIMESTAMP	NOT NULL DEFAULT CURRENT_TIMESTAMP,
	address				INTEGER		REFERENCES address(id),
	confidence			INTEGER		REFERENCES confidence(id),
	abuse				VARCHAR		REFERENCES concept(id),
	category			VARCHAR		REFERENCES concept(id),
	tagpack				INTEGER		REFERENCES tagpack(id) ON DELETE CASCADE
);

CREATE INDEX label_index ON tag (label);


-- GraphSense mapping table

CREATE TABLE address_cluster_mapping (
	address_id			INTEGER		REFERENCES address(id),
	gs_cluster_id 		INTEGER		NOT NULL,
	gs_cluster_def_addr	VARCHAR		NOT NULL,
	gs_cluster_no_addr	INTEGER		DEFAULT NULL,
	gs_cluster_in_degr	INTEGER		DEFAULT NULL,
	gs_cluster_out_degr INTEGER		DEFAULT NULL,
);


-- TODO: add triggers updating lastmod on update

