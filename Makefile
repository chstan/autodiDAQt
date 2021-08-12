#* Variables
SHELL := /usr/bin/env bash
PYTHON := python

#* Poetry
.PHONY: poetry-download
poetry-download:
	curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/install-poetry.py | $(PYTHON) -

.PHONY: poetry-remove
poetry-remove:
	curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/install-poetry.py | $(PYTHON) - --uninstall

#* Installation
.PHONY: install
install:
	poetry lock -n && poetry export --without-hashes > requirements.txt
	poetry install -n

.PHONY: pre-commit-install
pre-commit-install:
	echo "Pre-commit hook installation not supported. Need to migrate to lefthook."

#* Formatters
.PHONY: codestyle
codestyle:
	poetry run isort --settings-path pyproject.toml ./
	poetry run black --config pyproject.toml ./

.PHONY: formatting
formatting: codestyle

#* Linting
.PHONY: test
test:
	poetry run pytest -c pytest-config/pytest.ini

.PHONY: html-coverage
html-coverage:
	poetry run pytest -c pytest-config/pytest-coverage.ini
 
.PHONY: coverage
coverage: 
	poetry run pytest -c pytest-config/pytest-coverage-codecov.ini

.PHONY: check-codestyle
check-codestyle:
	poetry run isort --diff --check-only --settings-path pyproject.toml ./
	poetry run black --diff --check --config pyproject.toml ./
	poetry run darglint --verbosity 2 autodidaqt tests

.PHONY: lint
lint: test check-codestyle 

#* Cleaning
.PHONY: pycache-remove
pycache-remove:
	find . | grep -E "(__pycache__|\.pyc|\.pyo$$)" | xargs rm -rf

.PHONY: build-remove
build-remove:
	rm -rf build/

.PHONY: clean-all
clean-all: pycache-remove build-remove 
