FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates \
       curl \
       wget \
       libnss3 \
       libatk1.0-0 \
       libatk-bridge2.0-0 \
       libcups2 \
       libdrm2 \
       libxkbcommon0 \
       libxcomposite1 \
       libxdamage1 \
       libxfixes3 \
       libxrandr2 \
       libgbm1 \
       libxshmfence1 \
       libpango-1.0-0 \
       libpangocairo-1.0-0 \
       libasound2 \
       libatspi2.0-0 \
       libgtk-3-0 \
       fonts-liberation \
       libxcb-dri3-0 \
       libxcb-dri2-0 \
       libxcb-present0 \
       libxcb-sync1 \
       libxshmfence1 \
       libglu1-mesa \
       xvfb \
       unzip \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN python -m playwright install --with-deps

COPY app ./app

CMD ["python", "-u", "app/main.py"]
