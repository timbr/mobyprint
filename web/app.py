#!/usr/bin/env python3
"""mobyprint web UI — upload PDFs or DOCX files, preview pages, and print."""

import os
import uuid
import shutil
import time
import threading
from pathlib import Path

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
    send_file,
    abort,
)
from werkzeug.utils import secure_filename

from converter import (
    docx_to_pdf,
    scale_letter_to_a4,
    extract_pages,
    get_page_count,
    is_letter_size,
)
from ipp import (
    build_print_job,
    normalise_printer_url,
    parse_status,
    printer_http_url,
    send_ipp,
)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

UPLOAD_DIR = Path(os.environ.get("MOBYPRINT_UPLOAD_DIR", "/tmp/mobyprint"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_PRINTER = os.environ.get("PRINTER_URL", "")
ALLOWED_EXTENSIONS = {".pdf", ".docx"}
JOB_EXPIRY_SECONDS = 3600


def allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def create_job() -> tuple[str, Path]:
    job_id = uuid.uuid4().hex[:12]
    job_dir = UPLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / ".created").write_text(str(time.time()))
    return job_id, job_dir


def get_job_dir(job_id: str) -> Path:
    job_dir = UPLOAD_DIR / job_id
    if not job_dir.exists() or not job_dir.is_dir():
        abort(404, "Job not found")
    return job_dir


def get_job_pdf(job_id: str) -> Path:
    job_dir = get_job_dir(job_id)
    for name in ["scaled.pdf", "converted.pdf", "original.pdf"]:
        pdf = job_dir / name
        if pdf.exists():
            return pdf
    abort(404, "No PDF found for this job")


@app.route("/")
def index():
    return render_template("index.html", default_printer=DEFAULT_PRINTER)


@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename or not allowed_file(file.filename):
        return jsonify({"error": "Please upload a PDF or DOCX file."}), 400

    job_id, job_dir = create_job()
    filename = secure_filename(file.filename)
    suffix = Path(filename).suffix.lower()

    upload_path = job_dir / f"upload{suffix}"
    file.save(upload_path)

    if suffix == ".docx":
        try:
            pdf_path = docx_to_pdf(upload_path, job_dir)
            target = job_dir / "converted.pdf"
            pdf_path.rename(target)
            pdf_path = target
        except RuntimeError as e:
            shutil.rmtree(job_dir, ignore_errors=True)
            return jsonify({"error": f"Conversion failed: {e}"}), 500
    else:
        pdf_path = job_dir / "original.pdf"
        upload_path.rename(pdf_path)

    (job_dir / ".filename").write_text(filename)

    scale_to_a4 = request.form.get("scale_a4", "true") == "true"
    if scale_to_a4 and is_letter_size(pdf_path):
        try:
            scale_letter_to_a4(pdf_path, job_dir / "scaled.pdf")
        except Exception:
            pass

    return redirect(url_for("preview", job_id=job_id))


@app.route("/preview/<job_id>")
def preview(job_id: str):
    job_dir = get_job_dir(job_id)
    pdf_path = get_job_pdf(job_id)
    page_count = get_page_count(pdf_path)

    filename = "Document"
    filename_file = job_dir / ".filename"
    if filename_file.exists():
        filename = filename_file.read_text().strip()

    is_scaled = (job_dir / "scaled.pdf").exists()

    return render_template(
        "preview.html",
        job_id=job_id,
        page_count=page_count,
        filename=filename,
        is_scaled=is_scaled,
        default_printer=DEFAULT_PRINTER,
    )


@app.route("/api/pdf/<job_id>")
def serve_pdf(job_id: str):
    pdf_path = get_job_pdf(job_id)
    return send_file(pdf_path, mimetype="application/pdf")


@app.route("/api/print", methods=["POST"])
def api_print():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    job_id = data.get("job_id")
    printer_url = (data.get("printer") or "").strip()
    if not job_id:
        return jsonify({"error": "No job_id provided"}), 400
    if not printer_url:
        return jsonify({"error": "Printer URL is required."}), 400

    pages = data.get("pages")
    copies = int(data.get("copies", 1))

    pdf_path = get_job_pdf(job_id)

    if pages is not None and len(pages) > 0:
        job_dir = get_job_dir(job_id)
        print_pdf = job_dir / "print.pdf"
        extract_pages(pdf_path, print_pdf, pages)
    else:
        print_pdf = pdf_path

    pdf_bytes = print_pdf.read_bytes()
    printer_url = normalise_printer_url(printer_url)

    job_name = "mobyprint"
    filename_file = get_job_dir(job_id) / ".filename"
    if filename_file.exists():
        job_name = filename_file.read_text().strip()

    ipp_data = build_print_job(printer_url, pdf_bytes, job_name, copies, "mobyprint")
    http_url = printer_http_url(printer_url)

    try:
        http_status, response = send_ipp(http_url, ipp_data)
    except ConnectionRefusedError:
        return jsonify({"error": f"Could not connect to printer at {printer_url}. Is it on?"}), 502
    except OSError as e:
        return jsonify({"error": str(e)}), 502

    if http_status != 200:
        return jsonify({"error": f"Printer returned HTTP {http_status}."}), 502

    ipp_status, description = parse_status(response)
    if ipp_status is not None and ipp_status < 0x0300:
        return jsonify({"success": True, "message": f'"{job_name}" sent to printer.'})

    return jsonify({"error": f"Printer error: {description}"}), 502


def cleanup_old_jobs():
    now = time.time()
    if not UPLOAD_DIR.exists():
        return
    for job_dir in UPLOAD_DIR.iterdir():
        if not job_dir.is_dir():
            continue
        created_file = job_dir / ".created"
        if created_file.exists():
            try:
                created = float(created_file.read_text())
                if now - created > JOB_EXPIRY_SECONDS:
                    shutil.rmtree(job_dir, ignore_errors=True)
            except (ValueError, OSError):
                pass


def start_cleanup_thread():
    def loop():
        while True:
            time.sleep(300)
            cleanup_old_jobs()

    t = threading.Thread(target=loop, daemon=True)
    t.start()


if __name__ == "__main__":
    start_cleanup_thread()
    port = int(os.environ.get("PORT", 80))
    app.run(host="0.0.0.0", port=port)
