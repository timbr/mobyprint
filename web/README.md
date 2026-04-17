# mobyprint — Docker web service

A browser-based print UI that runs as a Docker container on any always-on Linux
machine (Raspberry Pi, home server, NAS, etc.). Uses
[Avahi](https://avahi.org) to advertise itself as `mobyprint.local` on your
local network, so you just type that into your phone's browser.

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

## Project layout

```
web/
├── app.py              # Flask application
├── ipp.py              # IPP protocol library
├── templates/
│   └── index.html      # Upload / print UI
├── Dockerfile
├── docker-compose.yml
├── avahi-daemon.conf   # Sets advertised hostname to "mobyprint"
└── entrypoint.sh       # Container init: dbus → avahi → Flask
```
