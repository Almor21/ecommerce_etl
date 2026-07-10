FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    ECOMMERCE_DATA_DIR=/app/data
WORKDIR /app

COPY requirements.txt ./
RUN pip install --require-hashes -r requirements.txt

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-deps .

COPY data/raw ./data/raw

CMD ["etl"]
