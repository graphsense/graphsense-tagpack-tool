SHELL := /bin/bash
PROJECT := tagpack-tool
VENV := .venv
RELEASE := 'v25.01.0a7'
# RELEASESEM := 'v1.9.0'

-include .env

all: format lint test build

tag-version:
	git diff --exit-code && git diff --staged --exit-code && git tag -a $(RELEASE) -m 'Release $(RELEASE)' || (echo "Repo is dirty please commit first" && exit 1)

serve:
	gs_tagstore_db_url='postgresql+asyncpg://${POSTGRES_USER_TAGSTORE}:${POSTGRES_PASSWORD_TAGSTORE}@localhost:5432/tagstore' uvicorn --reload --log-level debug src.tagstore.web.main:app

test:
	pytest -v -m "not slow" --cov=src

dev:
	 pip install -e .[dev]
	 pre-commit install

test-all:
	pytest --cov=src

install-dev: dev
	pip install -e .

install:
	pip install .

lint:
	ruff check tests src

format:
	ruff check --select I --fix .
	ruff format .

pre-commit:
	pre-commit run --all-files

build:
	tox -e clean
	tox -e build

tpublish: build version
	tox -e publish

publish: build version
	tox -e publish -- --repository pypi

version:
	python -m setuptools_scm


package-ui:
	- rm -rf admin-ui/dist
	cd admin-ui; npx elm-land build && cp  dist/assets/index-*.js ../src/tagstore/web/statics/assets/index.js

.PHONY: all test install lint format build pre-commit docs test-all docs-latex publish tpublish tag-version postgres-reapply-config serve package-ui
