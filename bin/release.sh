#!/usr/bin/env bash
# Release hook for VPS / Docker deploys: run after the image is built and before
# (or as) the web process starts. On Render these steps run via render.yaml
# (collectstatic in buildCommand, migrate in preDeployCommand) instead.
set -o errexit

python manage.py migrate --no-input
python manage.py collectstatic --no-input
