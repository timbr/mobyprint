# mobyprint — Docker web service

A browser-based print UI that runs as a Docker container on any always-on Linux
machine (Raspberry Pi, home server, NAS, etc.). Upload PDFs or DOCX files from
your phone, preview and select pages, then print to your network printer.

Uses [Avahi](https://avahi.org) to advertise itself as `mobyprint.local` on
your local network.

## Features

- **PDF and DOCX** — upload either format; DOCX is converted to PDF via LibreOffice
- **Letter to A4** — scales US Letter pages to fit A4 without reflowing text
- **Page selection** — visual thumbnails with tap-to-select, or type a range like `1-3, 5`
- **IPP printing** — sends directly to your network printer, no CUPS needed

## Requirements

- Docker + Docker Compose on a Linux host (Raspberry Pi works great)
- A network printer that supports IPP (most printers made after ~2010)
- Phone and host on the same Wi-Fi network

## Quick start

```bash
git clone https://github.com/timbr/mobyprint.git
cd mobyprint/web

docker compose up -d
```

Then open **`http://localhost:8080`** in your browser.

## `mobyprint.local` on Linux / Raspberry Pi

On a Linux host (where `network_mode: host` works), Avahi running inside the
container can advertise the name `mobyprint.local` via mDNS — so any device on
your network can reach the UI by name without knowing the IP address.

```bash
docker compose --profile host-net up -d
# → open http://mobyprint.local on any device on the same network
```

```
entrypoint.sh
  ├─ dbus-daemon        (required by avahi)
  ├─ avahi-daemon       (avahi-daemon.conf sets host-name=mobyprint)
  │    └─ broadcasts "mobyprint.local" via mDNS on the host network
  └─ python app.py      (Flask UI on port 80)
```

This does **not** work on Docker Desktop (Mac / Windows) because host
networking is not supported there.

## Configuration

| Environment variable | Default | Description |
|---|---|---|
| `PRINTER_URL` | _(empty)_ | Pre-fills the printer URL field in the UI |
| `PORT` | `80` | Port Flask listens on inside the container |

Set variables in a `.env` file next to `docker-compose.yml`:

```
PRINTER_URL=ipp://192.168.1.100/ipp/print
```

## How it works

```
Phone Browser  -->  Flask (port 80)  -->  IPP  -->  Network Printer
                      |
                 LibreOffice headless (DOCX → PDF)
                 pypdf (page extraction, Letter → A4 scaling)
```

1. Upload a PDF or DOCX from your phone's browser
2. DOCX files are converted to PDF using LibreOffice headless
3. If the document is US Letter and "Scale to A4" is on, pages are geometrically scaled to fit A4 (no text reflow)
4. Browse page thumbnails (rendered client-side with PDF.js), tap to select
5. Hit print — selected pages are sent to your printer via IPP

## Project layout

```
web/
├── app.py              # Flask application (upload, preview, print)
├── ipp.py              # IPP protocol library
├── converter.py        # DOCX→PDF, Letter→A4 scaling, page extraction
├── requirements.txt    # Python dependencies
├── templates/
│   ├── index.html      # Upload page
│   └── preview.html    # Page preview + selection + print
├── static/
│   └── style.css       # Mobile-first responsive styles
├── Dockerfile
├── docker-compose.yml
├── avahi-daemon.conf   # Sets advertised hostname to "mobyprint"
└── entrypoint.sh       # Container init: dbus → avahi → Flask
```
