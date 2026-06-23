# Optional container image for the quant-loop daemon.
#   docker build -f deploy/Dockerfile -t quant-loop .
#   docker run -d --name quant-loop --restart always \
#     -v quant-loop-state:/app/state \
#     -e ANTHROPIC_API_KEY=sk-...   quant-loop
#
# The named volume persists state/ (the journal + evolved skills) across restarts.

FROM python:3.12-slim
WORKDIR /app
COPY . .

# The core loop is stdlib-only. Uncomment for the real-model backend (--claude):
# RUN pip install --no-cache-dir anthropic

ENV PYTHONUNBUFFERED=1
STOPSIGNAL SIGTERM

# Production cadence; add --claude to use real models.
ENTRYPOINT ["python3", "run.py", "--serve", "--tick", "1m", "--ingest-every", "1h", "--risk-every", "1m"]
