# API image for x86_64 and ARM64 (Oracle Ampere) hosts.
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_ENV=production \
    PORT=8000 \
    OMP_NUM_THREADS=2 \
    OPENBLAS_NUM_THREADS=2 \
    MKL_NUM_THREADS=2

WORKDIR /app

# libgomp: CatBoost/LightGBM/XGBoost runtime. coinor-cbc: solver fallback when
# the bundled PuLP binary does not match the CPU. build-essential: only for
# any dependency without a prebuilt wheel on this architecture.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 libstdc++6 coinor-cbc build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt \
    && python -m pip check \
    && apt-get purge -y build-essential && apt-get autoremove -y

COPY project_paths.py ./
COPY model ./model
COPY intelligence ./intelligence
COPY data_processing ./data_processing
COPY data ./data
COPY pipeline ./pipeline

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/outputs /app/data/processed \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=180s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/live', timeout=4).status == 200 else 1)"
CMD ["python", "-m", "pipeline.serve"]
