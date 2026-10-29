# Sandbox image for generated connectors (TRD §2). Contains only the runner and the runtime:
# no app server, no vault, no LLM client. The connector module is mounted read-only per run.
ARG BASE_IMAGE=python:3.12-slim
FROM ${BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
COPY docker/runner-requirements.txt /tmp/requirements.txt
# An optional CA bundle (secret "ca") is only for build machines behind a TLS-inspecting proxy.
RUN --mount=type=secret,id=ca,required=false \
    if [ -s /run/secrets/ca ]; then export PIP_CERT=/run/secrets/ca; fi; \
    pip install --no-cache-dir -r /tmp/requirements.txt && rm /tmp/requirements.txt

WORKDIR /sandbox
COPY backend/runtime ./runtime
COPY backend/runner ./runner
COPY backend/app/__init__.py ./app/__init__.py
COPY backend/app/models/__init__.py ./app/models/__init__.py
COPY backend/app/models/canonical.py ./app/models/canonical.py

RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin sandbox
USER 10001
ENTRYPOINT ["python", "-m", "runner"]
