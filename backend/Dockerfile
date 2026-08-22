# syntax=docker/dockerfile:1.7

# ═══════════════════════════════════════════════════════════════════════
# Stage 1 — builder: install Python deps into an isolated prefix.
# ═══════════════════════════════════════════════════════════════════════
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build deps for asyncpg / bcrypt / cryptography wheels that may need compile,
# plus wget + ca-certificates for fetching the TA-Lib C library source tarball.
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        build-essential \
        libpq-dev \
        wget \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# TA-Lib C library — required by the ta-lib Python wrapper at compile + runtime.
# No apt package on slim images, so compile from upstream release. The Python
# wrapper version (in pyproject.toml) MUST match this major.minor.
ARG TA_LIB_VERSION=0.6.4
RUN set -eux; \
    cd /tmp; \
    wget -q https://github.com/ta-lib/ta-lib/releases/download/v${TA_LIB_VERSION}/ta-lib-${TA_LIB_VERSION}-src.tar.gz; \
    tar -xzf ta-lib-${TA_LIB_VERSION}-src.tar.gz; \
    cd ta-lib-${TA_LIB_VERSION}/; \
    ./configure --prefix=/usr; \
    make -j"$(nproc)"; \
    make install; \
    cd /; \
    rm -rf /tmp/ta-lib-${TA_LIB_VERSION} /tmp/ta-lib-${TA_LIB_VERSION}-src.tar.gz

WORKDIR /build

# ── Dependency layer ───────────────────────────────────────────────────
# Keyed ONLY on pyproject.toml, so editing app/ no longer reinstalls all
# 31 dependencies. Previously `COPY app ./app` sat ABOVE the install, so
# any source change invalidated it and every deploy re-resolved numpy,
# pyarrow, ta-lib and the rest: ~5 min and ~2 GB of layer churn each time,
# on a root volume that reached 96% full.
#
# chr(10) rather than '\n' keeps the newline out of the shell's hands —
# the RUN body is passed through /bin/sh, which would otherwise eat the
# escape before Python ever sees it.
COPY pyproject.toml README.md ./
RUN pip install --upgrade pip \
    && python -c "import tomllib,sys; [sys.stdout.write(d+chr(10)) for d in tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']]" > /tmp/requirements.txt \
    && pip install --prefix=/install -r /tmp/requirements.txt

# ── Project layer ──────────────────────────────────────────────────────
# Source arrives AFTER the dependencies. --no-deps because they are
# already in /install; this layer is only hatchling packaging our own
# code, which is what makes a source-only change cheap to rebuild.
COPY app ./app
RUN pip install --prefix=/install-app --no-deps "."

# ═══════════════════════════════════════════════════════════════════════
# Stage 2 — runtime: slim image, non-root user, healthcheck, uvloop CMD.
# ═══════════════════════════════════════════════════════════════════════
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/usr/local/bin:${PATH}"

# Only the runtime libraries — no compilers in the final image.
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system appgroup \
    && useradd --system --gid appgroup --home-dir /app --shell /usr/sbin/nologin appuser

# Two prefixes, two COPYs, deliberately. The dependency prefix is keyed on
# pyproject.toml alone, so this ~700 MB layer stays CACHED across source-only
# changes; our own package rides in a separate, tiny layer below. Merging both
# into one /install (the obvious version) silently defeats the split — the
# runtime COPY re-exports the whole 700 MB whenever app/ changes.
COPY --from=builder /install /usr/local
COPY --from=builder /install-app /usr/local

# TA-Lib runtime shared library copied from builder — the slim runtime stage
# never compiles, so we ship just the .so files. ldconfig refreshes the linker
# cache so `import talib` resolves libta-lib.so.0 at startup.
COPY --from=builder /usr/lib/libta-lib.so* /usr/lib/
RUN ldconfig

WORKDIR /app

COPY --chown=appuser:appgroup app ./app
COPY --chown=appuser:appgroup alembic.ini ./alembic.ini
COPY --chown=appuser:appgroup migrations ./migrations
COPY --chown=appuser:appgroup scripts ./scripts
# Phase 1 Strategy Template seed data (consumed by
# app.templates.scripts.seed_strategy_templates at deploy time +
# referenced by tests that load the JSON for shape assertions).
COPY --chown=appuser:appgroup data ./data

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--loop", "uvloop", \
     "--http", "httptools", \
     "--proxy-headers"]
