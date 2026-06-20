FROM python:3.11-slim

WORKDIR /workspace

RUN apt-get update && \
    apt-get install -y --no-install-recommends git ripgrep && \
    rm -rf /var/lib/apt/lists/*

COPY . .

RUN pip install --no-cache-dir rich openai rapidfuzz

ENV ORCA_PROJECT_ROOT=/workspace
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "orca.py"]
CMD ["--help"]
