"""
tools/pdf_to_pages.py
---------------------
ADK tool: Convert a PDF file into individual page PNG images.

Uses pdf2image (requires poppler installed on the system).
"""

from __future__ import annotations

from pathlib import Path

# ── Output directory for page images ─────────────────────────────────────────
OUTPUT_DIR = Path("images_output").resolve()
PAGES_DIR = OUTPUT_DIR / "pages"
PAGES_DIR.mkdir(parents=True, exist_ok=True)


def convert_pdf_to_pages(pdf_path: str, dpi: int = 300) -> dict:
    """Convert every page of a PDF to PNG images and return their paths.

    Call this tool when you receive a PDF file and need to process it
    page by page. Each page is saved as a high-resolution PNG image
    under images_output/pages/.

    Args:
        pdf_path: Absolute path to the PDF file on disk.
        dpi: Rendering resolution in dots per inch. Default 300 gives
            high-quality output suitable for OCR and visual detection.

    Returns:
        dict: A dictionary with:
            - status: "success" or "error"
            - page_paths: List of absolute paths to saved page PNG files
            - page_count: Number of pages converted
            - error_message: Error detail if status is "error"
    """
    try:
        from pdf2image import convert_from_path
    except ImportError:
        return {
            "status": "error",
            "error_message": (
                "pdf2image is required. Install with:\n"
                "  pip install pdf2image\n"
                "  brew install poppler   # macOS\n"
                "  apt install poppler-utils  # Linux"
            ),
        }

    if not Path(pdf_path).is_file():
        return {
            "status": "error",
            "error_message": f"PDF file not found: {pdf_path}",
        }

    try:
        pages = convert_from_path(pdf_path, dpi=dpi)
        paths: list[str] = []

        for i, page in enumerate(pages):
            out = PAGES_DIR / f"page_{i + 1:03d}.png"
            page.save(str(out), "PNG")
            paths.append(str(out))

        return {
            "status": "success",
            "page_paths": paths,
            "page_count": len(paths),
        }
    except Exception as exc:
        return {
            "status": "error",
            "error_message": str(exc),
        }
