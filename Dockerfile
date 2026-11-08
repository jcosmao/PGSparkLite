# PGSparkLite - runs on Raspberry Pi (arm64 / armv7) and x86_64

FROM debian:trixie-slim AS build
ENV DEBIAN_FRONTEND=noninteractive PIP_NO_CACHE_DIR=1
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip python3-dev gcc libsqlite3-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements-docker.txt /tmp/
RUN pip3 wheel --wheel-dir /wheels -r /tmp/requirements-docker.txt

FROM debian:trixie-slim
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_BREAK_SYSTEM_PACKAGES=1 \
    PGSPARKLITE_DB=/data/pgsparklite.db \
    FLASK_APP=app.py

# python3-bluez provides the 'bluetooth' module (RFCOMM to the amp)
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip python3-bluez \
    && rm -rf /var/lib/apt/lists/*

COPY --from=build /wheels /wheels
RUN pip3 install --no-index --find-links /wheels /wheels/*.whl && rm -rf /wheels

WORKDIR /app
COPY . .

VOLUME /data
EXPOSE 5000

CMD ["python3", "-m", "flask", "run", "--host=0.0.0.0", "--port=5000"]
