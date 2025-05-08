FROM python:3.9-slim-buster AS builder

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
WORKDIR /app


RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /app/wheels -r requirements.txt


FROM python:3.9-slim-buster

WORKDIR /app
ENV FLASK_APP=run.py
ENV FLASK_CONFIG=production
ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1


RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*


COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt

RUN groupadd -r appgroup && useradd --no-log-init -r -g appgroup -d /home/appuser -s /sbin/nologin -c "Application User" appuser \
    && mkdir -p /home/appuser/app && chown -R appuser:appgroup /home/appuser \
    && chown -R appuser:appgroup /app

COPY . .
RUN chown -R appuser:appgroup /app

USER appuser
WORKDIR /app

EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "run:app"]