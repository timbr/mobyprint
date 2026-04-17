"""Document conversion utilities for mobyprint.

Handles DOCX to PDF conversion via LibreOffice, Letter to A4 scaling,
and page extraction using pypdf.
"""

import subprocess
from pathlib import Path

from pypdf import PdfReader, PdfWriter, Transformation
from pypdf.generic import RectangleObject

LETTER_WIDTH, LETTER_HEIGHT = 612, 792
A4_WIDTH, A4_HEIGHT = 595.28, 841.89


def docx_to_pdf(docx_path: Path, output_dir: Path) -> Path:
    result = subprocess.run(
        [
            "libreoffice",
            "--headless",
            "--norestore",
            "--convert-to", "pdf",
            "--outdir", str(output_dir),
            str(docx_path),
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"LibreOffice conversion failed: {result.stderr}")

    pdf_path = output_dir / docx_path.with_suffix(".pdf").name
    if not pdf_path.exists():
        raise RuntimeError(
            f"Expected PDF not found at {pdf_path}. "
            f"LibreOffice output: {result.stdout}"
        )
    return pdf_path


def scale_letter_to_a4(input_pdf: Path, output_pdf: Path) -> Path:
    reader = PdfReader(input_pdf)
    writer = PdfWriter()

    for page in reader.pages:
        media = page.mediabox
        page_w = float(media.width)
        page_h = float(media.height)

        sx = A4_WIDTH / page_w
        sy = A4_HEIGHT / page_h
        scale = min(sx, sy)

        scaled_w = page_w * scale
        scaled_h = page_h * scale
        offset_x = (A4_WIDTH - scaled_w) / 2
        offset_y = (A4_HEIGHT - scaled_h) / 2

        page.add_transformation(
            Transformation()
            .scale(scale, scale)
            .translate(offset_x / scale, offset_y / scale)
        )
        page.mediabox = RectangleObject([0, 0, A4_WIDTH, A4_HEIGHT])
        writer.add_page(page)

    with open(output_pdf, "wb") as f:
        writer.write(f)

    return output_pdf


def extract_pages(input_pdf: Path, output_pdf: Path, pages: list[int]) -> Path:
    reader = PdfReader(input_pdf)
    writer = PdfWriter()

    for page_num in pages:
        if 0 <= page_num < len(reader.pages):
            writer.add_page(reader.pages[page_num])

    with open(output_pdf, "wb") as f:
        writer.write(f)

    return output_pdf


def get_page_count(pdf_path: Path) -> int:
    return len(PdfReader(pdf_path).pages)


def is_letter_size(pdf_path: Path, tolerance: float = 10) -> bool:
    reader = PdfReader(pdf_path)
    if not reader.pages:
        return False
    media = reader.pages[0].mediabox
    w, h = float(media.width), float(media.height)
    return abs(w - LETTER_WIDTH) < tolerance and abs(h - LETTER_HEIGHT) < tolerance
