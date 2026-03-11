#!/bin/sh
set -eu

cd /app
export PRODUCTION=1

python -OO app.py
