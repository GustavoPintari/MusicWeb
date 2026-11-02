# MusicWeb in a container (Podman or Docker), for a Linux server.
# The "Receiver" output is mpv playing through the host's PipeWire (its socket is mounted by the Quadlet),
# which owns the sound card, e.g. the P2 jack or a USB DAC.
#
#   podman build -t localhost/musicweb .
#
# See deploy/ (Quadlet + config) and the "Linux server (Podman)" section of the README.
FROM docker.io/library/debian:trixie-slim

# pipewire (client.conf) and libpipewire-0.3-modules (the native protocol) are what let mpv's --ao=pipewire
# connect to the host socket; without them it fails with "Failed to initialize audio driver 'pipewire'"
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-mutagen mpv alsa-utils ca-certificates tzdata \
      pipewire libpipewire-0.3-modules \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY server.py ./
COPY musicweb ./musicweb
COPY deploy/config.server.toml /etc/musicweb/config.toml

# the config can be replaced by mounting another file over /etc/musicweb/config.toml
ENV MUSICWEB_CONFIG=/etc/musicweb/config.toml \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

VOLUME ["/music", "/trash", "/data", "/cache"]
EXPOSE 8095
STOPSIGNAL SIGTERM
CMD ["python3", "/app/server.py"]
