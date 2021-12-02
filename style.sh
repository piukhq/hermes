#!/bin/sh

pipenv run black --line-length 120 . && \
pipenv run flake8 . && \
pipenv run isort --line-length 120 --profile black . && \
pipenv run xenon --no-assert --max-average A --max-modules B --max-absolute B .
