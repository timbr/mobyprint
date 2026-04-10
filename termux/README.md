# mobyprint — Termux CLI

A self-contained Python script that prints PDFs from your Android phone via
[Termux](https://termux.dev). No external libraries required — only the Python
standard library.

## Install

```bash
git clone https://github.com/timbr/mobyprint.git
cd mobyprint/termux
bash setup.sh
```

`setup.sh` installs Python (if missing) and copies `mobyprint` to `$PREFIX/bin`.

## Usage

### Print a PDF

```bash
mobyprint print document.pdf --printer ipp://192.168.1.100/ipp/print
```

Common IPP paths to try if `/ipp/print` doesn't work:

| Printer / server | Path |
|---|---|
| Most HP, Canon, Epson | `/ipp/print` |
| CUPS server | `/printers/PRINTER_NAME` |
| Some Brother models | `/ipp` |

### Check printer connectivity

```bash
mobyprint info --printer ipp://192.168.1.100/ipp/print
```

### Discover printers automatically

Requires `avahi` (mDNS browser):

```bash
pkg install avahi
avahi-daemon &
mobyprint discover
```

### All options

```
mobyprint print FILE --printer URL [--copies N] [--job-name NAME] [--username NAME] [-v]
mobyprint info       --printer URL [-v]
mobyprint discover   [--timeout SECONDS]
```

## Finding your printer's IP

- Check the printer's own display (Network / Wi-Fi settings menu)
- Check your router's connected-devices / DHCP client list
- Print a network configuration page from the printer

You can also use the `.local` hostname if your network supports mDNS:

```bash
mobyprint print document.pdf --printer ipp://MYHP.local/ipp/print
```

## How it works

`mobyprint.py` builds a raw IPP `Print-Job` request and posts it over HTTP to
port 631 on the printer — the same protocol used by AirPrint. Everything runs
in a single Python file with no external dependencies.
