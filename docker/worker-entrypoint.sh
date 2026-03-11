#!/bin/sh
set -eu

cd /app

python -OO worker.py
