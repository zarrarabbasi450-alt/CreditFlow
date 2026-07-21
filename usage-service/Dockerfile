FROM python:3.14-slim AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /build
COPY pyproject.toml requirements.txt ./
COPY src ./src
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --upgrade pip && /opt/venv/bin/pip install .

FROM python:3.14-slim AS runtime
ENV PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
RUN addgroup --system --gid 1001 creditflow && adduser --system --uid 1001 --ingroup creditflow usage
COPY --from=builder /opt/venv /opt/venv
USER usage
EXPOSE 8005
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8005/health', timeout=2)"]
CMD ["uvicorn", "usage_service.main:app", "--host", "0.0.0.0", "--port", "8005", "--proxy-headers", "--no-server-header"]
