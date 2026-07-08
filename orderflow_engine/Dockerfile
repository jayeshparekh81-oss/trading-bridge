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
COPY verify_session.py config.yaml holidays.yaml ./

# Recorded data lives on a mounted volume.
VOLUME ["/app/data"]

CMD ["python", "-m", "recorder.main"]
