# orderflow_engine / recorder — standalone image (Module R0)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Kolkata

WORKDIR /app

# tzdata so zoneinfo("Asia/Kolkata") resolves inside the slim image
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY recorder ./recorder
# Analysis packages (2026-07-16): the same image runs the one-shot `evening_pipeline`
# service (tape/levels/chain/signals/alerts + the Daily Pulse). The recorder daemon
# ignores these; they add no runtime weight to it. Without them the evening chain
# ModuleNotFound-fails.
COPY tape ./tape
COPY levels ./levels
COPY chain ./chain
COPY signals ./signals
COPY alerts ./alerts
COPY replayer ./replayer
COPY verify_session.py config.yaml tape_config.yaml holidays.yaml events.yaml ./

# Recorded data lives on a mounted volume.
VOLUME ["/app/data"]

CMD ["python", "-m", "recorder.main"]
