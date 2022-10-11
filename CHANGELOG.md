The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [1.1.0] Unreleased
### Added
- Support for connection pooling
- Removal of duplicate tags
### Fixed
- Fix cluster mapping of ETH addresses without external txs
- consolidate tagpack-level properties
- `conda` setup

## [1.0.1] 2022-08-26
### Added
- Optional prefix for tagpack
- View for tag count by cluster 
- View for cluster defining tags by frequency and maxconfidence 
### Fixed
- Bug with --add_new flag

## [1.0.0] 2022-07-14
### Changed
- improved ingest: improved schema validation feedback for user, remove duplicates in tagpacks
- generate tagpack base URI automatically (no longer necessary to keep config.yaml up-to-date)
- updated confidence.csv 
### Added
- YAML file inclusion to share a header file between multiple tagpack files
- encourage clean tagpack repository when ingesting tagpacks (can be disabled with command line options `--no_strict_check` and `--no_git`)
- URI field in TagStore database to support backlink to tagpack repository in the dashboard
- option to ingest all taxonomies at once instead of one taxonomy at a time
- command line option `--config` to supply path to config file
- command line option `--force` to force re-ingest if tagpack already is present in database
- command line option `--add_new` to skip over ingested tagpacks and ingest only new ones

## [0.5.2] 2022-03-24
### Changed
- **Tagstore design:** migrate tag handling from Cassandra keyspaces
  to external tag store(s)
- tagpack validation of confidence value, which is now categorical
  instead of numerical
### Added
- check for duplicate entries
- database view for tag statistics
### Removed
- entity-related components
### Fixed
- bug in tag validation

# [0.5.1] 2021-11-17
## Changed
- versions of third party library dependencies
## Added
- additional schema fields
- command line tool usability fixes
- support for dev version numbers

## [0.5.0] 2021-05-31
### Changed
- Switched to GitHub action workflows
- Added support for entity tags
- Move TagPack documentation to TagPack rep
- Update package dependencies

### Added
- Add additional TagPack validation tests
- Add support for Entity Tags

### Removed
- Removed unnecessary lookup tables

## [0.4.4] - 2020-06-12
### Fixed
- Fixed PEP8 warnings (`flake8`)

## [0.4.3] - 2020-05-11
### Changed
- Separated TagPack Management Tool from public TagPacks
- Refactored scripts into TagPack Management tool
- Re-implemented validation and ingest procedures

### Added
- Support for ingestion / validation of remote taxonomy concepts

## [0.4.2] - 2019-12-19
### Added
- New tagpacks
- Abuses field

### Changed
- Splitted config from schema
- Improved argparse
- Renaming categories

### Removed
- Jupyter notebooks

## [0.4.1] - 2019-06-28
### Added
- Tagpacks: walletexplorer, ransomware, sextortion (Talos), miners
- Schema creation, validate and ingest scripts
- Documentation, License, etc.
