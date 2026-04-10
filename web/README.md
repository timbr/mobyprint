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

# Optional: pre-fill the printer URL in the UI
export PRINTER_URL=ipp://192.168.1.100/ipp/print

docker compose up -d
```

Then open **`http://mobyprint.local`** on any device on your network.

## How `mobyprint.local` works

`docker-compose.yml` uses `network_mode: host`, which means the container
shares the host's real network interface. Avahi running inside the container
broadcasts the name `mobyprint.local` via mDNS multicast — exactly the same
mechanism a Raspberry Pi uses for its own hostname. Any device on the network
with mDNS support (all modern phones, Macs, and Linux desktops) can resolve it.

```
docker compose up
  └─ entrypoint.sh
       ├─ dbus-daemon        (required by avahi)
       ├─ avahi-daemon       (avahi-daemon.conf sets host-name=mobyprint)
       │    └─ broadcasts "mobyprint.local" via mDNS on the host network
       └─ python app.py      (Flask UI on port 80)
```

## Configuration

| Environment variable | Default | Description |
|---|---|---|
| `PRINTER_URL` | _(empty)_ | Pre-fills the printer URL field in the UI |
| `PORT` | `80` | Port Flask listens on |

Set variables in a `.env` file next to `docker-compose.yml`:

```
PRINTER_URL=ipp://192.168.1.100/ipp/print
```

## Docker Desktop (Mac / Windows)

`network_mode: host` is only supported on Linux. On Docker Desktop use the
`bridge` profile — you'll access the UI at `http://localhost:8080` instead:

```bash
docker compose --profile bridge up -d
```

On macOS the OS handles `.local` resolution natively (Bonjour), so if you set
your host machine's hostname to `mobyprint` it will be reachable as
`mobyprint.local` without anything extra from Docker.

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
