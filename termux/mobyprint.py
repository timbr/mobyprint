#!/usr/bin/env python3
"""mobyprint - Print PDFs from your phone using Termux via IPP."""

import argparse
import http.client
import os
import socket
import ssl
import struct
import subprocess
import sys
import urllib.parse

# IPP version
IPP_VERSION_MAJOR = 2
IPP_VERSION_MINOR = 0

# IPP operation IDs
OP_PRINT_JOB = 0x0002
OP_GET_PRINTER_ATTRS = 0x000B

# Attribute group delimiter tags
TAG_OPERATION = 0x01
TAG_JOB = 0x02
TAG_END = 0x03

# Attribute value syntax tags
TAG_INTEGER = 0x21
TAG_BOOLEAN = 0x22
TAG_ENUM = 0x23
TAG_KEYWORD = 0x44
TAG_URI = 0x45
TAG_CHARSET = 0x47
TAG_NATURAL_LANGUAGE = 0x48
TAG_MIME_MEDIA_TYPE = 0x49
TAG_NAME_WITHOUT_LANG = 0x42
TAG_TEXT_WITHOUT_LANG = 0x41


def encode_attr(value_tag, name, value):
    """Encode a single IPP attribute into bytes."""
    name_b = name.encode("utf-8")
    if value_tag in (
        TAG_KEYWORD, TAG_URI, TAG_CHARSET, TAG_NATURAL_LANGUAGE,
        TAG_MIME_MEDIA_TYPE, TAG_NAME_WITHOUT_LANG, TAG_TEXT_WITHOUT_LANG,
    ):
        value_b = value.encode("utf-8")
    elif value_tag in (TAG_INTEGER, TAG_ENUM):
        value_b = struct.pack(">i", value)
    elif value_tag == TAG_BOOLEAN:
        value_b = struct.pack(">B", 1 if value else 0)
    else:
        value_b = value

    return (
        struct.pack(">B", value_tag)
        + struct.pack(">H", len(name_b))
        + name_b
        + struct.pack(">H", len(value_b))
        + value_b
    )


def build_print_job(printer_uri, pdf_bytes, job_name, copies, username):
    """Build a complete IPP Print-Job request."""
    op_attrs = (
        encode_attr(TAG_CHARSET, "attributes-charset", "utf-8")
        + encode_attr(TAG_NATURAL_LANGUAGE, "attributes-natural-language", "en")
        + encode_attr(TAG_URI, "printer-uri", printer_uri)
        + encode_attr(TAG_NAME_WITHOUT_LANG, "requesting-user-name", username)
        + encode_attr(TAG_NAME_WITHOUT_LANG, "job-name", job_name)
        + encode_attr(TAG_MIME_MEDIA_TYPE, "document-format", "application/pdf")
        + encode_attr(TAG_BOOLEAN, "ipp-attribute-fidelity", False)
    )

    job_attrs = encode_attr(TAG_INTEGER, "copies", copies)

    header = struct.pack(
        ">BBHI",
        IPP_VERSION_MAJOR,
        IPP_VERSION_MINOR,
        OP_PRINT_JOB,
        1,  # request-id
    )

    return (
        header
        + struct.pack(">B", TAG_OPERATION)
        + op_attrs
        + struct.pack(">B", TAG_JOB)
        + job_attrs
        + struct.pack(">B", TAG_END)
        + pdf_bytes
    )


def build_get_printer_attrs(printer_uri):
    """Build an IPP Get-Printer-Attributes request."""
    op_attrs = (
        encode_attr(TAG_CHARSET, "attributes-charset", "utf-8")
        + encode_attr(TAG_NATURAL_LANGUAGE, "attributes-natural-language", "en")
        + encode_attr(TAG_URI, "printer-uri", printer_uri)
        + encode_attr(TAG_KEYWORD, "requested-attributes", "printer-state")
    )

    header = struct.pack(
        ">BBHI",
        IPP_VERSION_MAJOR,
        IPP_VERSION_MINOR,
        OP_GET_PRINTER_ATTRS,
        2,
    )

    return header + struct.pack(">B", TAG_OPERATION) + op_attrs + struct.pack(">B", TAG_END)


def parse_status(data):
    """Return (status_code, description) from an IPP response."""
    if len(data) < 8:
        return None, "response too short to parse"
    _, _, status_code, _ = struct.unpack(">BBHI", data[:8])
    descriptions = {
        0x0000: "successful-ok",
        0x0001: "successful-ok-ignored-or-substituted-attributes",
        0x0002: "successful-ok-conflicting-attributes",
        0x0400: "client-error-bad-request",
        0x0401: "client-error-forbidden",
        0x0403: "client-error-not-authenticated",
        0x0404: "client-error-not-authorized",
        0x0405: "client-error-not-possible",
        0x0406: "client-error-timeout",
        0x0407: "client-error-not-found",
        0x0408: "client-error-gone",
        0x040A: "client-error-request-entity-too-large",
        0x040D: "client-error-document-format-not-supported",
        0x0500: "server-error-internal-error",
        0x0503: "server-error-service-unavailable",
        0x0505: "server-error-version-not-supported",
    }
    desc = descriptions.get(status_code, f"unknown (0x{status_code:04x})")
    return status_code, desc


def send_ipp(printer_url, ipp_data, verbose=False):
    """Send IPP data over HTTP/HTTPS and return (http_status, response_bytes)."""
    parsed = urllib.parse.urlparse(printer_url)
    host = parsed.hostname
    port = parsed.port or 631
    path = parsed.path or "/ipp/print"
    if not path:
        path = "/ipp/print"

    use_tls = parsed.scheme in ("ipps", "https")

    if verbose:
        print(f"  Connecting to {host}:{port}{path} (TLS={use_tls})")

    if use_tls:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        conn = http.client.HTTPSConnection(host, port, timeout=30, context=ctx)
    else:
        conn = http.client.HTTPConnection(host, port, timeout=30)

    headers = {
        "Content-Type": "application/ipp",
        "Content-Length": str(len(ipp_data)),
        "Accept": "application/ipp",
        "Connection": "close",
    }

    conn.request("POST", path, body=ipp_data, headers=headers)
    resp = conn.getresponse()
    body = resp.read()
    conn.close()
    return resp.status, body


def printer_http_url(printer_url):
    """Convert an ipp:// or ipps:// URL to http:// or https:// for the connection."""
    return (
        printer_url
        .replace("ipp://", "http://")
        .replace("ipps://", "https://")
    )


def normalise_printer_url(url):
    """Ensure the printer URL has a recognised scheme."""
    if "://" not in url:
        return "ipp://" + url
    return url


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_print(args):
    if not os.path.exists(args.file):
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    with open(args.file, "rb") as f:
        pdf_bytes = f.read()

    if pdf_bytes[:4] != b"%PDF":
        print("Warning: file does not look like a PDF (missing %PDF header)", file=sys.stderr)

    printer_url = normalise_printer_url(args.printer)
    job_name = args.job_name or os.path.basename(args.file)
    username = args.username or os.environ.get("USER", "termux-user")

    print(f"Printer : {printer_url}")
    print(f"File    : {args.file} ({len(pdf_bytes):,} bytes)")
    print(f"Job     : {job_name}")
    print(f"Copies  : {args.copies}")

    ipp_data = build_print_job(printer_url, pdf_bytes, job_name, args.copies, username)
    http_url = printer_http_url(printer_url)

    try:
        http_status, response = send_ipp(http_url, ipp_data, verbose=args.verbose)
    except ConnectionRefusedError:
        print(f"\nError: connection refused by {printer_url}", file=sys.stderr)
        print("Is the printer on and reachable from this network?", file=sys.stderr)
        sys.exit(1)
    except socket.timeout:
        print("\nError: connection timed out", file=sys.stderr)
        sys.exit(1)
    except OSError as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.verbose:
        print(f"  HTTP status: {http_status}")

    if http_status != 200:
        print(f"\nError: printer returned HTTP {http_status}", file=sys.stderr)
        sys.exit(1)

    ipp_status, description = parse_status(response)
    if ipp_status is not None and ipp_status < 0x0300:
        print(f"\nPrint job submitted successfully ({description})")
    else:
        print(f"\nPrinter rejected the job: {description}", file=sys.stderr)
        sys.exit(1)


def cmd_info(args):
    """Query basic info from a printer."""
    printer_url = normalise_printer_url(args.printer)
    http_url = printer_http_url(printer_url)
    print(f"Querying {printer_url} ...")

    ipp_data = build_get_printer_attrs(printer_url)
    try:
        http_status, response = send_ipp(http_url, ipp_data, verbose=args.verbose)
    except (ConnectionRefusedError, socket.timeout, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    if http_status != 200:
        print(f"HTTP {http_status}", file=sys.stderr)
        sys.exit(1)

    ipp_status, description = parse_status(response)
    if ipp_status is not None and ipp_status < 0x0300:
        print(f"Printer is reachable ({description})")
    else:
        print(f"Printer responded with: {description}", file=sys.stderr)
        sys.exit(1)


def cmd_discover(args):
    """Attempt to discover IPP printers on the local network."""
    found = []

    # 1. Try avahi-browse (available after: pkg install avahi)
    try:
        result = subprocess.run(
            ["avahi-browse", "-t", "-r", "-p", "_ipp._tcp"],
            capture_output=True, text=True, timeout=args.timeout,
        )
        for line in result.stdout.splitlines():
            if not line.startswith("="):
                continue
            parts = line.split(";")
            if len(parts) < 9:
                continue
            name = parts[3]
            host = parts[6].rstrip(".")
            port = parts[8]
            txt = parts[9] if len(parts) > 9 else ""
            rp = "ipp/print"
            for field in txt.split('"'):
                if field.startswith("rp="):
                    rp = field[3:]
                    break
            url = f"ipp://{host}:{port}/{rp}"
            found.append((name, url))
    except FileNotFoundError:
        pass  # avahi not installed
    except subprocess.TimeoutExpired:
        pass

    if found:
        print(f"Found {len(found)} printer(s):\n")
        for name, url in found:
            print(f"  {name}")
            print(f"    {url}\n")
    else:
        print("No printers found automatically.\n")
        print("Options:")
        print("  1. Install avahi and retry:")
        print("       pkg install avahi")
        print("       avahi-daemon &")
        print("       mobyprint discover\n")
        print("  2. Find your printer's IP address manually (check its display or")
        print("     your router's device list) and use it directly:\n")
        print("       mobyprint print document.pdf --printer ipp://PRINTER_IP/ipp/print\n")
        print("  3. Use the printer hostname if your network supports mDNS:")
        print("       mobyprint print document.pdf --printer ipp://PRINTER.local/ipp/print")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        prog="mobyprint",
        description="Print PDFs from your phone using Termux.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="verbose output")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # print
    p_print = sub.add_parser("print", help="send a PDF to a printer")
    p_print.add_argument("file", help="PDF file to print")
    p_print.add_argument(
        "--printer", "-p", required=True,
        metavar="URL",
        help="printer URL, e.g. ipp://192.168.1.100/ipp/print",
    )
    p_print.add_argument("--job-name", "-n", metavar="NAME", help="job name (default: filename)")
    p_print.add_argument("--copies", "-c", type=int, default=1, metavar="N", help="number of copies (default: 1)")
    p_print.add_argument("--username", "-u", metavar="NAME", help="requesting user name")
    p_print.set_defaults(func=cmd_print)

    # info
    p_info = sub.add_parser("info", help="check connectivity to a printer")
    p_info.add_argument("--printer", "-p", required=True, metavar="URL", help="printer URL")
    p_info.set_defaults(func=cmd_info)

    # discover
    p_disc = sub.add_parser("discover", help="find printers on the local network")
    p_disc.add_argument("--timeout", "-t", type=int, default=5, metavar="S", help="search timeout in seconds (default: 5)")
    p_disc.set_defaults(func=cmd_discover)

    args = parser.parse_args()

    # propagate verbose to subcommands that accept it
    if not hasattr(args, "verbose"):
        args.verbose = False

    args.func(args)


if __name__ == "__main__":
    main()
