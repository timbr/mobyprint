#!/usr/bin/env python3
"""mobyprint web UI — upload a PDF and send it to a printer."""

import os

from flask import Flask, render_template, request

from mobyprint import (
    build_print_job,
    normalise_printer_url,
    parse_status,
    printer_http_url,
    send_ipp,
)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB

DEFAULT_PRINTER = os.environ.get("PRINTER_URL", "")


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", default_printer=DEFAULT_PRINTER)


@app.route("/print", methods=["POST"])
def print_pdf():
    printer_url = request.form.get("printer_url", "").strip()
    copies = max(1, int(request.form.get("copies") or 1))
    job_name = request.form.get("job_name", "").strip()
    file = request.files.get("file")

    def fail(msg):
        return render_template("index.html", default_printer=printer_url, error=msg), 400

    if not file or not file.filename:
        return fail("No file selected.")
    if not printer_url:
        return fail("Printer URL is required.")

    pdf_bytes = file.read()
    if not pdf_bytes:
        return fail("Uploaded file is empty.")

    job_name = job_name or file.filename
    printer_url = normalise_printer_url(printer_url)

    ipp_data = build_print_job(printer_url, pdf_bytes, job_name, copies, "web-user")
    http_url = printer_http_url(printer_url)

    try:
        http_status, response = send_ipp(http_url, ipp_data)
    except ConnectionRefusedError:
        return fail(f"Could not connect to printer at {printer_url}. Is it on and reachable?")
    except OSError as exc:
        return fail(str(exc))

    if http_status != 200:
        return fail(f"Printer returned HTTP {http_status}.")

    ipp_status, description = parse_status(response)
    if ipp_status is not None and ipp_status < 0x0300:
        return render_template(
            "index.html",
            default_printer=printer_url,
            success=f'"{job_name}" sent to printer.',
        )

    return fail(f"Printer error: {description}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 80))
    app.run(host="0.0.0.0", port=port)
