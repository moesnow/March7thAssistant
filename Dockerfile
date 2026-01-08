FROM python:3.13-slim

# Avoid interactive prompts from debconf during apt operations
ARG DEBIAN_FRONTEND=noninteractive
ENV DEBIAN_FRONTEND=${DEBIAN_FRONTEND}

# Python optimization for containerized apps
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Activate venv by updating PATH
ENV VIRTUAL_ENV="/opt/venv"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

WORKDIR /m7a

COPY . /m7a/

RUN \
    # sed -i 's/deb.debian.org/mirrors.cloud.tencent.com/g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -yq --no-install-recommends \
    # Dependencies for pyzbar
    libzbar0 \
    # Dependencies for OpenCV
    libgl1 \
    # Dependencies for headless Chrome
    libglib2.0-0 \
    libnss3 \
    libfontconfig1 \
    libx11-6 \
    libx11-xcb1 \
    libxcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libxkbcommon0 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libpango-1.0-0 \
    libgtk-3-0 \
    ca-certificates \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/* \
    && python -m venv $VIRTUAL_ENV \
    && pip install --no-cache-dir -r requirements-docker.txt \
    # -i https://mirrors.cloud.tencent.com/pypi/simple/ \
    && python build.py --task ocr \
    && python build.py --task browser

CMD ["python", "main.py"]