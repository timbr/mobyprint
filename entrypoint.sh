#!/bin/bash
set -e

# dbus is required by avahi-daemon
mkdir -p /run/dbus
dbus-daemon --system --fork 2>/dev/null || true

# Advertise mobyprint.local on the host network.
# --no-rlimits: skip rlimit enforcement (safe inside a container).
# -D: daemonise.
avahi-daemon --no-rlimits -D 2>/dev/null || true

# Hand off to Flask
exec python app.py
