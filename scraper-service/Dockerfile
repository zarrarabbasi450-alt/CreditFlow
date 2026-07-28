FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app/src
WORKDIR /app

COPY requirements.txt .
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt \
    && python -m playwright install --with-deps chromium

COPY . .

EXPOSE 8110
# Default role is the API. Run the same image as the worker instead with:
#   docker run ... <image> python -m scraper_service.worker
# Both must be running for scrape jobs to actually execute — see README.
CMD ["uvicorn", "scraper_service.main:app", "--host", "0.0.0.0", "--port", "8110"]
