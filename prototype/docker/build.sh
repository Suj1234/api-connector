#!/bin/sh
# Builds the two sandbox images. On a normal Mac/Linux machine: ./docker/build.sh
# Behind a TLS-inspecting proxy, also set CA_BUNDLE=/path/to/ca.pem (and BASE_IMAGE for a mirror).
set -e
cd "$(dirname "$0")/.."
BASE="${BASE_IMAGE:-python:3.12-slim}"
SECRET=""
if [ -n "$CA_BUNDLE" ]; then SECRET="--secret id=ca,src=$CA_BUNDLE"; fi
PY="${PYTHON:-.venv/bin/python}"
FINGERPRINT=$(PYTHONPATH=backend "$PY" -c "from app.services.sandbox import source_fingerprint; print(source_fingerprint())")
docker build $SECRET $DOCKER_BUILD_ARGS --build-arg BASE_IMAGE="$BASE" --label source_fingerprint="$FINGERPRINT" \
  -f docker/runner.Dockerfile -t integration-runner:dev .
docker build $DOCKER_BUILD_ARGS --build-arg BASE_IMAGE="$BASE" -f docker/egress-proxy/Dockerfile -t integration-egress:dev .
echo "Sandbox images ready: integration-runner:dev ($FINGERPRINT), integration-egress:dev"
