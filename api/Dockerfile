# Build from the REPOSITORY ROOT (the engine, the three shared src/ modules and data/factor_table.json live outside api/):
#   docker build -f api/Dockerfile -t msi-api .
#   docker run --rm -p 8080:8080 -e PORT=8080 -e MSI_CORS_ORIGINS=https://your-frontend.example msi-api
# Python 3.11 on purpose: the engine golden numbers are generated with 3.11 (3.12 changes sum() rounding).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

COPY api/requirements.txt /app/api/requirements.txt
RUN pip install --no-cache-dir -r /app/api/requirements.txt

# engine is stdlib-only; it imports exactly these three modules from src/ (through engine/_src.py) and reads data/factor_table.json
COPY engine/ /app/engine/
COPY src/companion_kits.py src/companion_python_model.py src/status_timeline.py /app/src/
COPY data/factor_table.json /app/data/factor_table.json
COPY data/cube_potential_data.json /app/data/cube_potential_data.json
COPY api/__init__.py api/cache.py api/features.py api/main.py api/middleware.py api/registry.py api/settings.py api/validation.py /app/api/

RUN useradd --system --no-create-home app
USER app

# Cloud Run injects $PORT; one worker (instances scale horizontally, the in-memory rate limiter is per instance)
CMD ["sh", "-c", "exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT}"]
