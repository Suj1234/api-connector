# Per-run egress proxy (TRD §2): the sandbox's only way out. Allows CONNECT to one host on 443.
ARG BASE_IMAGE=python:3.12-slim
FROM ${BASE_IMAGE}
COPY docker/egress-proxy/proxy.py /proxy.py
USER 65534
EXPOSE 3128
CMD ["python", "-u", "/proxy.py"]
