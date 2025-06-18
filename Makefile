SHELL := /bin/bash
PROJECT := tagpack-tool
VENV := .venv
RELEASE := 'v25.07.3'
# RELEASESEM := 'v1.9.0'

-include .env

gs_tagstore_db_url ?= 'postgresql+asyncpg://${POSTGRES_USER_TAGSTORE}:${POSTGRES_PASSWORD_TAGSTORE}@localhost:5432/tagstore'

all: format lint test build

tag-version:
	git diff --exit-code && git diff --staged --exit-code && git tag -a $(RELEASE) -m 'Release $(RELEASE)' || (echo "Repo is dirty please commit first" && exit 1)

serve:
	@gs_tagstore_db_url=${gs_tagstore_db_url} uv run uvicorn --reload --log-level debug src.tagstore.web.main:app

test:
	uv run pytest -x -rx -vv -m "not slow" --cov=tagpack --cov=tagstore --capture=no

dev:
	 uv sync --all-extras --dev
	 pre-commit install

test-all:
	uv run pytest -x -rx -vv --cov=tagpack --cov=tagstore --capture=no

install-dev: dev
	uv pip install -e .

install:
	uv pip install .

lint:
	uv run ruff check tests src

format:
	uv run ruff check --select I --fix .
	uv run ruff format .

pre-commit:
	uv run pre-commit run --all-files

build:
	uv run tox -e clean
	uv run tox -e build

version:
	uv run python -m setuptools_scm

package-ui:
	- rm -rf admin-ui/dist
	cd admin-ui; npx elm-land build && cp  dist/assets/index-*.js ../src/tagstore/web/statics/assets/index.js

build-docker:
	docker build -t tagpack-tool .

.PHONY: all test install lint format build pre-commit docs test-all docs-latex publish tpublish tag-version postgres-reapply-config serve package-ui build-docker
