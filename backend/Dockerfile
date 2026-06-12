# =============================================================================
# Backend — Supplier Risk Scan Agent (FastAPI)
# =============================================================================
FROM python:3.12-slim AS builder

ENV \
  UV_COMPILE_BYTECODE=1 \
  UV_LINK_MODE=copy

# Install uv into /bin
COPY --from=ghcr.io/astral-sh/uv:0.6 /uv /uvx /bin/

WORKDIR /app

# Install dependencies (cached until lockfile changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# ── Runtime stage ────────────────────────────────────────────────────────────
FROM python:3.12-slim

# Create a non-root user
RUN addgroup --system --gid 1001 app && \
    adduser --system --uid 1001 --gid 1001 app

# Copy the .venv from builder (uv binary not needed at runtime)
COPY --from=builder /app/.venv /app/.venv

# Make .venv binaries available on PATH
ENV PATH=/app/.venv/bin:$PATH

WORKDIR /app

# Copy application code
COPY . .

# Ensure ownership
RUN chown -R app:app /app

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
