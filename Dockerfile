FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    PORT=8000 \
    OMP_NUM_THREADS=1 \
    OPENBLAS_NUM_THREADS=1 \
    MKL_NUM_THREADS=1

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 libstdc++6 \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt && python -m pip check
COPY model ./model
COPY intelligence ./intelligence
COPY data_processing ./data_processing
COPY data ./data
COPY pipeline ./pipeline
COPY tests ./tests
COPY project_paths.py run_daily_sync.py ./
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/outputs /app/data/processed \
    && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
CMD ["python", "-m", "pipeline.serve"]
