"""Mobyprint - Mobile printing web application.

Upload PDFs or DOCX files from your phone, preview pages,
select which ones to print, and send them to your network printer.
"""

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
from printer import list_printers, print_file

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB upload limit

UPLOAD_DIR = Path(os.environ.get("MOBYPRINT_UPLOAD_DIR", "/tmp/mobyprint"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".docx"}
JOB_EXPIRY_SECONDS = 3600  # Clean up jobs after 1 hour


def allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def create_job() -> tuple[str, Path]:
    """Create a new job directory and return (job_id, job_dir)."""
    job_id = uuid.uuid4().hex[:12]
    job_dir = UPLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    # Touch a timestamp file for cleanup
    (job_dir / ".created").write_text(str(time.time()))
    return job_id, job_dir


def get_job_dir(job_id: str) -> Path:
    """Get job directory, raising 404 if it doesn't exist."""
    job_dir = UPLOAD_DIR / job_id
    if not job_dir.exists() or not job_dir.is_dir():
        abort(404, "Job not found")
    return job_dir


def get_job_pdf(job_id: str) -> Path:
    """Get the PDF path for a job (either original or converted)."""
    job_dir = get_job_dir(job_id)
    # Look for the scaled A4 version first, then original PDF
    for name in ["scaled.pdf", "converted.pdf", "original.pdf"]:
        pdf = job_dir / name
        if pdf.exists():
            return pdf
    abort(404, "No PDF found for this job")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename or not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type. Please upload a PDF or DOCX file."}), 400

    job_id, job_dir = create_job()
    filename = secure_filename(file.filename)
    suffix = Path(filename).suffix.lower()

    # Save uploaded file
    upload_path = job_dir / f"upload{suffix}"
    file.save(upload_path)

    # Convert DOCX to PDF if needed
    if suffix == ".docx":
        try:
            pdf_path = docx_to_pdf(upload_path, job_dir)
            # Rename to a consistent name
            target = job_dir / "converted.pdf"
            pdf_path.rename(target)
            pdf_path = target
        except RuntimeError as e:
            shutil.rmtree(job_dir, ignore_errors=True)
            return jsonify({"error": f"Conversion failed: {e}"}), 500
    else:
        pdf_path = job_dir / "original.pdf"
        upload_path.rename(pdf_path)

    # Store original filename for display
    (job_dir / ".filename").write_text(filename)

    # Check if Letter-sized and auto-scale to A4
    scale_to_a4 = request.form.get("scale_a4", "true") == "true"
    if scale_to_a4 and is_letter_size(pdf_path):
        try:
            scaled_path = job_dir / "scaled.pdf"
            scale_letter_to_a4(pdf_path, scaled_path)
        except Exception:
            pass  # Fall back to unscaled version

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
    )


@app.route("/api/pdf/<job_id>")
def serve_pdf(job_id: str):
    """Serve the PDF file for client-side rendering with PDF.js."""
    pdf_path = get_job_pdf(job_id)
    return send_file(pdf_path, mimetype="application/pdf")


@app.route("/api/printers")
def api_printers():
    try:
        printers = list_printers()
        return jsonify(printers)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/print", methods=["POST"])
def api_print():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    job_id = data.get("job_id")
    if not job_id:
        return jsonify({"error": "No job_id provided"}), 400

    pages = data.get("pages")  # List of 0-based page indices
    printer_name = data.get("printer")  # None for default
    copies = int(data.get("copies", 1))

    pdf_path = get_job_pdf(job_id)

    # Extract selected pages if specified
    if pages is not None and len(pages) > 0:
        job_dir = get_job_dir(job_id)
        print_pdf = job_dir / "print.pdf"
        extract_pages(pdf_path, print_pdf, pages)
    else:
        print_pdf = pdf_path

    try:
        job = print_file(
            pdf_path=print_pdf,
            printer_name=printer_name if printer_name else None,
            copies=copies,
            media="A4",
        )
        return jsonify({"success": True, "job_id": job})
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500


def cleanup_old_jobs():
    """Remove job directories older than JOB_EXPIRY_SECONDS."""
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
    """Run periodic cleanup in a background thread."""
    def loop():
        while True:
            time.sleep(300)  # Check every 5 minutes
            cleanup_old_jobs()

    t = threading.Thread(target=loop, daemon=True)
    t.start()


if __name__ == "__main__":
    start_cleanup_thread()
    port = int(os.environ.get("MOBYPRINT_PORT", 8631))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "0") == "1")
