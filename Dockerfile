# Single-stage Dockerfile (the original "multi-stage" build was broken: the
# second FROM threw away everything the first stage produced and reinstalled
# everything from scratch — wasted build time and image size).
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1

# System deps: gcc/libffi for compiling `cryptg` & `tgcrypto`, ffmpeg for
# thumbnail screenshots, git for the GitHub-fork pip installs.
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
        musl-dev \
        git \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel \
    && pip install -r requirements.txt \
    && pip install tgcrypto

COPY . .

CMD ["bash", "bash.sh"]
