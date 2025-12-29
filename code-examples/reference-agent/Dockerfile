# Reference Agent - Production Dockerfile
# Chapter 1: The Production Mindset
#
# This Dockerfile demonstrates production best practices:
# - Multi-stage build for smaller images
# - Non-root user for security
# - Minimal base image
# - Health checks
# - Proper dependency management

# ============================================================================
# Stage 1: Builder
# ============================================================================
FROM python:3.11-slim as builder

# Install uv for fast, reliable dependency management
RUN pip install --no-cache-dir uv==0.1.0

# Set working directory
WORKDIR /app

# Copy only dependency files first (for better caching)
COPY pyproject.toml ./

# Create virtual environment and install dependencies
RUN uv venv /opt/venv && \
    . /opt/venv/bin/activate && \
    uv pip install -e .

# ============================================================================
# Stage 2: Runtime
# ============================================================================
FROM python:3.11-slim

# Install runtime dependencies (if any)
# For this simple agent, we don't need additional system packages

# Create non-root user for security
RUN useradd -m -u 1000 agent && \
    mkdir -p /app /app/logs /app/data && \
    chown -R agent:agent /app

# Set working directory
WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder --chown=agent:agent /opt/venv /opt/venv

# Copy application code
COPY --chown=agent:agent agent.py config.py tools.py ./

# Switch to non-root user
USER agent

# Activate virtual environment
ENV PATH="/opt/venv/bin:$PATH"

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ANTHROPIC_API_KEY="" \
    AGENT_MODEL="claude-3-5-sonnet-20241022" \
    AGENT_MAX_TOKENS=4096 \
    AGENT_MAX_ITERATIONS=10

# Health check (basic - will be improved in Chapter 2)
# For now, just check if Python can import the agent module
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import agent; print('healthy')" || exit 1

# Labels for metadata
LABEL maintainer="Production AI Agents Book" \
      version="0.1.0" \
      description="Reference agent - baseline for production hardening" \
      chapter="1"

# Default command: Run the agent in interactive mode
CMD ["python", "agent.py"]
