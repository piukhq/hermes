#!/bin/sh

pipenv run flake8 . && \
pipenv run xenon --no-assert --max-average A --max-modules B --max-absolute B .
