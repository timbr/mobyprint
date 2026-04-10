#!/usr/bin/env bash
# mobyprint setup script for Termux
# Run once after cloning the repo:
#   bash setup.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$PREFIX/bin"   # Termux puts its binaries here

echo "==> mobyprint setup"

# Check we're in Termux (or a compatible environment)
if [ -z "$PREFIX" ]; then
    # Fallback for non-Termux Linux
    INSTALL_DIR="$HOME/.local/bin"
    mkdir -p "$INSTALL_DIR"
    echo "    (non-Termux environment detected, installing to $INSTALL_DIR)"
fi

# Ensure Python 3 is available
if ! command -v python3 &>/dev/null; then
    echo "==> Python 3 not found. Installing via pkg..."
    pkg install python -y
fi

echo "    Python 3 found: $(python3 --version)"

# Install the script
cp "$SCRIPT_DIR/mobyprint.py" "$INSTALL_DIR/mobyprint"
chmod +x "$INSTALL_DIR/mobyprint"

echo "==> mobyprint installed to $INSTALL_DIR/mobyprint"

# Make sure INSTALL_DIR is on PATH
if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
    echo ""
    echo "    NOTE: $INSTALL_DIR is not in your PATH."
    echo "    Add this to your ~/.bashrc or ~/.zshrc:"
    echo "      export PATH=\"$INSTALL_DIR:\$PATH\""
fi

echo ""
echo "Done! Quick start:"
echo ""
echo "  # Check a printer is reachable"
echo "  mobyprint info --printer ipp://PRINTER_IP/ipp/print"
echo ""
echo "  # Print a PDF"
echo "  mobyprint print document.pdf --printer ipp://PRINTER_IP/ipp/print"
echo ""
echo "  # Auto-discover printers (requires avahi):"
echo "  pkg install avahi && avahi-daemon &"
echo "  mobyprint discover"
