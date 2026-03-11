#!/bin/sh
set -eu

cd /app

mkdir -p /app/dist/static
if [ -d /app/vue-cutter/public/static ]; then
  cp -rn /app/vue-cutter/public/static/. /app/dist/static/ || true
fi

python -OO worker.py
