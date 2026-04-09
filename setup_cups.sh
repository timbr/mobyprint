#!/usr/bin/env bash
#
# setup_cups.sh - Helper to configure a network printer in CUPS
#
# Usage:
#   ./setup_cups.sh                     # Interactive: scan and select a printer
#   ./setup_cups.sh <printer-ip>        # Add printer at the given IP
#   ./setup_cups.sh <printer-ip> <name> # Add printer with a custom name
#
# This script is meant to be run inside the Docker container or on the host
# where CUPS client tools are available.

set -euo pipefail

PRINTER_IP="${1:-}"
PRINTER_NAME="${2:-home-printer}"

discover_printers() {
    echo "Scanning for network printers..."
    echo ""

    # Try avahi/mDNS discovery first
    if command -v avahi-browse &>/dev/null; then
        echo "=== Printers found via mDNS (AirPrint/IPP) ==="
        avahi-browse -t -r _ipp._tcp 2>/dev/null | grep -E "(hostname|address|txt)" | head -30 || true
        echo ""
    fi

    # Also try CUPS browsing
    if command -v lpinfo &>/dev/null; then
        echo "=== Printers found via CUPS discovery ==="
        lpinfo --include-schemes ipp,ipps -v 2>/dev/null | head -20 || true
        echo ""
    fi
}

add_printer() {
    local ip="$1"
    local name="$2"
    local uri="ipp://${ip}/ipp/print"

    echo "Adding printer '${name}' at ${uri}..."

    # Try to add via lpadmin
    if command -v lpadmin &>/dev/null; then
        lpadmin -p "${name}" \
            -v "${uri}" \
            -E \
            -o media=A4 \
            -o printer-is-shared=false

        # Set as default if it's the only printer
        printer_count=$(lpstat -p 2>/dev/null | wc -l)
        if [ "${printer_count}" -le 1 ]; then
            lpadmin -d "${name}"
            echo "Set '${name}' as the default printer."
        fi

        echo "Printer '${name}' added successfully!"
        echo ""
        echo "Test with: echo 'Hello' | lp -d ${name}"
    else
        echo "Error: lpadmin not found. Install cups-client."
        exit 1
    fi
}

# Main
if [ -z "${PRINTER_IP}" ]; then
    discover_printers
    echo "---"
    echo "To add a printer, run:"
    echo "  $0 <printer-ip> [printer-name]"
    echo ""
    echo "Example:"
    echo "  $0 192.168.1.50 home-printer"
else
    add_printer "${PRINTER_IP}" "${PRINTER_NAME}"
fi
