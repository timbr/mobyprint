"""CUPS printer integration for mobyprint.

Lists available printers and submits print jobs.
Falls back to the `lp` command if pycups is unavailable.
"""

import subprocess
from pathlib import Path

try:
    import cups

    PYCUPS_AVAILABLE = True
except ImportError:
    PYCUPS_AVAILABLE = False


def list_printers() -> dict:
    """Return a dict of {printer_name: info_dict} for all CUPS printers.

    Each info_dict contains 'description', 'location', 'is_default', and 'state'.
    """
    if PYCUPS_AVAILABLE:
        return _list_printers_pycups()
    return _list_printers_lp()


def _list_printers_pycups() -> dict:
    conn = cups.Connection()
    printers = conn.getPrinters()
    default = conn.getDefault()
    result = {}
    for name, attrs in printers.items():
        result[name] = {
            "description": attrs.get("printer-info", name),
            "location": attrs.get("printer-location", ""),
            "is_default": name == default,
            "state": _printer_state(attrs.get("printer-state", 0)),
        }
    return result


def _list_printers_lp() -> dict:
    result = subprocess.run(
        ["lpstat", "-p", "-d"],
        capture_output=True, text=True,
    )
    printers = {}
    default_name = None

    for line in result.stdout.splitlines():
        if line.startswith("printer "):
            parts = line.split()
            name = parts[1]
            state = "idle" if "idle" in line else "busy"
            printers[name] = {
                "description": name,
                "location": "",
                "is_default": False,
                "state": state,
            }
        elif "system default destination:" in line:
            default_name = line.split(":")[-1].strip()

    if default_name and default_name in printers:
        printers[default_name]["is_default"] = True

    return printers


def print_file(
    pdf_path: Path,
    printer_name: str | None = None,
    copies: int = 1,
    page_ranges: str | None = None,
    media: str = "A4",
) -> str:
    """Print a PDF file to the specified CUPS printer.

    Args:
        pdf_path: Path to the PDF to print.
        printer_name: CUPS printer name. None for default printer.
        copies: Number of copies.
        page_ranges: Page range string like "1-3,5" (1-based). None for all.
        media: Paper size (e.g., "A4", "Letter").

    Returns:
        Job ID as a string.
    """
    if PYCUPS_AVAILABLE:
        return _print_pycups(pdf_path, printer_name, copies, page_ranges, media)
    return _print_lp(pdf_path, printer_name, copies, page_ranges, media)


def _print_pycups(
    pdf_path: Path,
    printer_name: str | None,
    copies: int,
    page_ranges: str | None,
    media: str,
) -> str:
    conn = cups.Connection()
    if printer_name is None:
        printer_name = conn.getDefault()
        if printer_name is None:
            printers = conn.getPrinters()
            if not printers:
                raise RuntimeError("No printers available")
            printer_name = next(iter(printers))

    options = {
        "copies": str(copies),
        "media": media,
    }
    if page_ranges:
        options["page-ranges"] = page_ranges

    job_id = conn.printFile(
        printer_name,
        str(pdf_path),
        pdf_path.stem,
        options,
    )
    return str(job_id)


def _print_lp(
    pdf_path: Path,
    printer_name: str | None,
    copies: int,
    page_ranges: str | None,
    media: str,
) -> str:
    cmd = ["lp"]
    if printer_name:
        cmd += ["-d", printer_name]
    cmd += ["-n", str(copies)]
    cmd += ["-o", f"media={media}"]
    if page_ranges:
        cmd += ["-o", f"page-ranges={page_ranges}"]
    cmd.append(str(pdf_path))

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"lp failed: {result.stderr}")

    # Parse job ID from output like "request id is PrinterName-123 (1 file(s))"
    output = result.stdout.strip()
    if "request id is" in output:
        return output.split("request id is")[1].split()[0]
    return output


def _printer_state(state_code: int) -> str:
    return {3: "idle", 4: "printing", 5: "stopped"}.get(state_code, "unknown")
