FROM python:3.12-slim

# avahi-daemon  — mDNS advertisement
# dbus          — required by avahi
RUN apt-get update && apt-get install -y --no-install-recommends \
        avahi-daemon \
        dbus \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir flask

WORKDIR /app
COPY ipp.py app.py ./
COPY templates/ templates/

# Override avahi config to advertise as "mobyprint"
COPY avahi-daemon.conf /etc/avahi/avahi-daemon.conf

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Port 80 is used directly via network_mode: host — no mapping needed.
# EXPOSE is informational only.
EXPOSE 80

CMD ["/entrypoint.sh"]
