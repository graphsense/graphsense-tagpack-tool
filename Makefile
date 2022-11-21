SHELL := /bin/bash
PROJECT := tagpack-tool
VENV := .venv

all: format lint test 

test:
	pytest -v -m "not slow" --cov=src

test-all:
	pytest --cov=src

install-dev:
	pip install -e .

install:
	pip install .

lint:
	flake8 bin/tagpack-tool tests tagpack

format:
	black tests tagpack bin/tagpack-tool --exclude _version.py
	
.PHONY: all test install lint format
