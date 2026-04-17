FROM python:3.12-slim

# avahi-daemon  — mDNS advertisement (mobyprint.local)
# dbus          — required by avahi
# libreoffice-writer — DOCX to PDF conversion
RUN apt-get update && apt-get install -y --no-install-recommends \
        avahi-daemon \
        dbus \
        libreoffice-writer \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

WORKDIR /app
COPY ipp.py app.py converter.py ./
COPY templates/ templates/
COPY static/ static/

COPY avahi-daemon.conf /etc/avahi/avahi-daemon.conf

COPY entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

RUN mkdir -p /tmp/mobyprint

EXPOSE 80

CMD ["/entrypoint.sh"]
