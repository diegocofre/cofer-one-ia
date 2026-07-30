# SPDX-License-Identifier: Apache-2.0
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
RUN pip install --no-cache-dir .

EXPOSE 11434
CMD ["uvicorn", "app.entrypoint:app", "--host", "0.0.0.0", "--port", "11434"]
