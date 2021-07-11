FROM python:3-buster as build
RUN python3 -m venv --copies /venv && /venv/bin/pip install --upgrade pip

FROM build AS build-venv
RUN apt-get update && apt-get install --no-install-suggests --no-install-recommends --yes \
    wget xz-utils \
    build-essential autoconf libtool pkg-config

RUN export ARCH="$(dpkg --print-architecture)" && \
    wget -O /tmp/ffmpeg.tar.xz "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-${ARCH}-static.tar.xz" && \
    tar xf /tmp/ffmpeg.tar.xz && mv "ffmpeg-4.4-${ARCH}-static" /opt/ffmpeg

COPY requirements.txt /requirements.txt
RUN /venv/bin/pip install --disable-pip-version-check -r /requirements.txt

FROM gcr.io/distroless/python3-debian10
COPY --from=build-venv /opt/ffmpeg /opt/ffmpeg
COPY --from=build-venv /usr/local/lib /usr/lib
COPY --from=build-venv /venv /venv

COPY . /app
WORKDIR /app

ENTRYPOINT ["/venv/bin/python", "server.py"]
