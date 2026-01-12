FROM python:3.13.11-slim-trixie

# Avoid interactive prompts from debconf during apt operations
ARG DEBIAN_FRONTEND=noninteractive
ENV DEBIAN_FRONTEND=${DEBIAN_FRONTEND}

# Python optimization for containerized apps
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Activate venv by updating PATH
ENV VIRTUAL_ENV="/opt/venv"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Set timezone
ENV TZ=Asia/Shanghai

# Set environment variables to enable specific features in the application
ENV MARCH7TH_CLOUD_GAME_ENABLE=true
ENV MARCH7TH_BROWSER_HEADLESS_ENABLE=true
ENV MARCH7TH_BROWSER_HEADLESS_RESTART_ON_NOT_LOGGED_IN=false
# 默认使用官方源下载浏览器；如果下载缓慢，可以改为 true 启用镜像下载
ENV MARCH7TH_BROWSER_DOWNLOAD_USE_MIRROR=false
# 任务完成后循环执行
ENV MARCH7TH_AFTER_FINISH=Loop
# 标记从 Docker 启动，避免控制台阻塞
ENV MARCH7TH_DOCKER_STARTED=true

WORKDIR /m7a

COPY requirements-docker.txt ./

RUN \
    # 如果需要使用国内源，可以取消下面一行的注释
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
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv $VIRTUAL_ENV \
    && pip install --no-cache-dir \
    # 如果需要使用国内源，可以取消下面一行的注释
    # -i https://mirrors.cloud.tencent.com/pypi/simple/ \
    -r requirements-docker.txt

COPY . .

RUN python build.py --task ocr \
    && python build.py --task browser

CMD ["python", "main.py"]