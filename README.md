# mobyprint

Send PDF files to a printer from your phone using [Termux](https://termux.dev).

Uses the **Internet Printing Protocol (IPP)** — the same standard used by AirPrint
and most modern network printers and CUPS servers. No extra apps or cloud services
needed; your phone and printer just need to be on the same Wi-Fi network.

## Requirements

- [Termux](https://termux.dev) on Android
- Python 3 (`pkg install python`)
- A network printer that supports IPP (most printers made after ~2010 do)

## Install

```bash
git clone https://github.com/timbr/mobyprint.git
cd mobyprint
bash setup.sh
```

`setup.sh` copies `mobyprint` to `$PREFIX/bin` so it is available as a command.

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

Requires `avahi` (mDNS/Bonjour browser):

```bash
pkg install avahi
avahi-daemon &
mobyprint discover
```

### Options

```
mobyprint print FILE --printer URL [--copies N] [--job-name NAME] [--username NAME]
mobyprint info       --printer URL
mobyprint discover   [--timeout SECONDS]
```

| Flag | Default | Description |
|---|---|---|
| `--copies`, `-c` | 1 | Number of copies |
| `--job-name`, `-n` | filename | Name shown in the printer queue |
| `--username`, `-u` | `$USER` | Requesting user name sent to printer |
| `--timeout`, `-t` | 5 | Discover timeout in seconds |
| `--verbose`, `-v` | off | Show connection details |

## Finding your printer's IP address

- Check the printer's own display (Network / Wi-Fi settings menu)
- Check your router's connected-devices / DHCP list
- Print a network configuration page from the printer

You can also use the printer's `.local` hostname if your network supports mDNS:

```bash
mobyprint print document.pdf --printer ipp://MYHP.local/ipp/print
```

## How it works

`mobyprint` builds a raw IPP/1.1 `Print-Job` request and sends it over HTTP to
port 631 on the printer. No external Python packages are required — only the
standard library (`http.client`, `struct`, `socket`).

## License

MIT
