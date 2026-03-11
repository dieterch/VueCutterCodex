#!/bin/sh
set -eu

cd /app
export PRODUCTION=1

mkdir -p /app/dist/static
if [ -d /app/vue-cutter/public/static ]; then
  cp -rn /app/vue-cutter/public/static/. /app/dist/static/ || true
fi

python -OO app.py
