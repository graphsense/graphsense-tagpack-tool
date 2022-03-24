The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).


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
