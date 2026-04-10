"""IPP (Internet Printing Protocol) client — shared library for mobyprint."""

import http.client
import socket
import ssl
import struct
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
    """Convert an ipp:// or ipps:// URL to http:// or https:// for the HTTP connection."""
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
