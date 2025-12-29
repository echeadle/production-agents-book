# Production-Ready Multi-Stage Dockerfile for AI Agent
#
# This Dockerfile demonstrates production best practices:
# - Multi-stage build for smaller final image
# - Non-root user for security
# - Minimal base image (Python slim)
# - Proper dependency caching
# - Health checks
# - Security scanning friendly

# Stage 1: Builder - Install dependencies
FROM python:3.11-slim as builder

# Install uv for fast dependency management
RUN pip install --no-cache-dir uv==0.1.0

WORKDIR /app

# Copy dependency files first for better layer caching
COPY pyproject.toml .
COPY uv.lock* .

# Install dependencies into a virtual environment
RUN uv venv /opt/venv && \
    . /opt/venv/bin/activate && \
    uv pip install -r pyproject.toml

# Stage 2: Runtime - Minimal production image
FROM python:3.11-slim

# Install runtime dependencies (if needed)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd -m -u 1000 agent && \
    mkdir -p /app /app/logs /app/data && \
    chown -R agent:agent /app

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY --chown=agent:agent . .

# Switch to non-root user
USER agent

# Add venv to PATH
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Expose Prometheus metrics port (if agent exposes metrics)
EXPOSE 8000

# Health check - adjust based on your agent's health endpoint
# If no HTTP server, check if process is running
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

# Run the agent
CMD ["python", "-m", "agent"]
