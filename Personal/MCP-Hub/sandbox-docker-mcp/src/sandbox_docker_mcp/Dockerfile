FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       bash build-essential ca-certificates curl git ripgrep \
    && rm -rf /var/lib/apt/lists/*

CMD ["sleep", "infinity"]
