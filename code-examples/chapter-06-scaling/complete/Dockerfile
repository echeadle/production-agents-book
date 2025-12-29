FROM python:3.11-slim as builder
RUN pip install --no-cache-dir uv==0.1.0
WORKDIR /app
COPY pyproject.toml ./
RUN uv venv /opt/venv && . /opt/venv/bin/activate && uv pip install -e .

FROM python:3.11-slim
RUN useradd -m -u 1000 agent && mkdir -p /app /app/logs /app/data && chown -R agent:agent /app
WORKDIR /app
COPY --from=builder --chown=agent:agent /opt/venv /opt/venv
COPY --chown=agent:agent *.py ./
USER agent
ENV PATH="/opt/venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
HEALTHCHECK --interval=30s --timeout=10s --retries=3 CMD python -c "import agent; print('healthy')" || exit 1
EXPOSE 8080
CMD ["python", "agent.py"]
