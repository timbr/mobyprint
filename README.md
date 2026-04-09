# Mobyprint

Print PDFs and DOCX files from your phone to your home network printer.

## Features

- **Upload from mobile** - Clean, tap-friendly web interface
- **PDF printing** - Upload a PDF, select specific pages, print
- **DOCX support** - Converts DOCX to PDF via LibreOffice (preserves complex formatting)
- **Letter to A4** - Scales US Letter pages to A4 without reflowing text or changing page boundaries
- **Page selection** - Visual page thumbnails with tap-to-select, or type a range like `1-3, 5`
- **CUPS printing** - Works with any network printer supported by CUPS

## Quick Start

### With Docker (recommended)

```bash
# Build and run
docker compose up -d --build

# Open on your phone's browser:
# http://<your-server-ip>:8631
```

### Configure your printer

Inside the container, use the setup helper to find and add your network printer:

```bash
# Scan for printers on the network
docker compose exec mobyprint ./setup_cups.sh

# Add a printer by IP
docker compose exec mobyprint ./setup_cups.sh 192.168.1.50 home-printer
```

Or if you know the printer's IPP URL, add it directly:

```bash
docker compose exec mobyprint \
  lpadmin -p home-printer -v ipp://192.168.1.50/ipp/print -E -o media=A4
```

### Without Docker

Requirements: Python 3.12+, LibreOffice, CUPS client tools, poppler-utils

```bash
pip install -r requirements.txt
python app.py
```

## How It Works

```
Phone Browser  -->  Flask (port 8631)  -->  CUPS  -->  Network Printer
                        |
                   LibreOffice headless (DOCX -> PDF)
                   pypdf (page extraction, Letter -> A4 scaling)
```

1. Upload a PDF or DOCX from your phone's browser
2. DOCX files are converted to PDF using LibreOffice headless
3. If the document is US Letter and "Scale to A4" is on, pages are geometrically scaled to fit A4 (no text reflow)
4. Browse page thumbnails (rendered client-side with PDF.js), tap to select
5. Hit print -- selected pages are sent to your CUPS printer

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `MOBYPRINT_PORT` | `8631` | Port the web server listens on |
| `MOBYPRINT_UPLOAD_DIR` | `/tmp/mobyprint` | Temp directory for uploaded files |
| `FLASK_DEBUG` | `0` | Set to `1` for development mode |

## Network Notes

The Docker container runs with `network_mode: host` so it can discover network printers via mDNS/Avahi. If you prefer isolated networking, use port mapping and configure the printer manually:

```yaml
# docker-compose.yml alternative
services:
  mobyprint:
    build: .
    ports:
      - "8631:8631"
    volumes:
      - uploads:/tmp/mobyprint
```
