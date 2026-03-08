"""
tools/crop_image.py
-------------------
ADK tool: Crop a region from a page image using normalized bounding-box
coordinates and save as a PNG file.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from PIL import Image

# ── Output directory for cropped images ──────────────────────────────────────
OUTPUT_DIR = Path("images_output").resolve()
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def crop_region(
    page_path: str,
    x_left: float,
    y_top: float,
    x_right: float,
    y_bottom: float,
    label: str = "",
) -> dict:
    """Crop a visual region from an exam-page image and save it as PNG.

    Call this tool whenever a question or option contains a visual element
    (circuit diagram, chemical structure, geometric shape, graph, map,
    paper-folding figure, Venn diagram, mirror image, equation image,
    or any non-text element) and you have its normalised bounding-box
    coordinates.

    The tool crops that region with a small padding buffer, saves it as
    a uniquely named PNG inside images_output/, and returns the absolute
    path so it can be embedded in the output JSON.

    Args:
        page_path: Absolute path to the source page image (PNG or JPG).
        x_left: Normalised left edge of the bounding box (0.0 to 1.0).
        y_top: Normalised top edge of the bounding box (0.0 to 1.0).
        x_right: Normalised right edge (must be > x_left).
        y_bottom: Normalised bottom edge (must be > y_top).
        label: Short human-readable tag for the filename, e.g.
            "q3_circuit" or "q7_optB_venn". Max 40 characters.

    Returns:
        dict: A dictionary with:
            - status: "success" or "error"
            - cropped_path: Absolute path to saved PNG (on success)
            - filename: Just the filename part (on success)
            - error_message: Error detail (on error)
    """
    # ── Validate file exists ─────────────────────────────────────────────────
    if not Path(page_path).is_file():
        return {
            "status": "error",
            "error_message": f"Page image not found: {page_path}",
        }

    # ── Validate coordinates ─────────────────────────────────────────────────
    coords = {"x_left": x_left, "y_top": y_top, "x_right": x_right, "y_bottom": y_bottom}
    for name, val in coords.items():
        if not (0.0 <= val <= 1.0):
            return {
                "status": "error",
                "error_message": f"{name}={val} is out of range [0.0, 1.0]",
            }

    if x_left >= x_right:
        return {
            "status": "error",
            "error_message": f"x_left ({x_left}) must be < x_right ({x_right})",
        }
    if y_top >= y_bottom:
        return {
            "status": "error",
            "error_message": f"y_top ({y_top}) must be < y_bottom ({y_bottom})",
        }

    try:
        # ── Load image ───────────────────────────────────────────────────────
        img = Image.open(page_path).convert("RGB")
        W, H = img.size

        # ── Denormalise → pixel coordinates with padding ─────────────────────
        PADDING = 4
        x0 = max(0, int(x_left * W) - PADDING)
        y0 = max(0, int(y_top * H) - PADDING)
        x1 = min(W - 1, int(x_right * W) + PADDING)
        y1 = min(H - 1, int(y_bottom * H) + PADDING)

        # ── Crop and save ────────────────────────────────────────────────────
        cropped = img.crop((x0, y0, x1, y1))

        uid = uuid.uuid4().hex[:12]
        safe_label = label.replace(" ", "_")[:40]
        filename = f"crop_{safe_label}_{uid}.png" if safe_label else f"crop_{uid}.png"

        out_path = OUTPUT_DIR / filename
        cropped.save(str(out_path), format="PNG")

        return {
            "status": "success",
            "cropped_path": str(out_path),
            "filename": filename,
        }

    except Exception as exc:
        return {
            "status": "error",
            "error_message": str(exc),
        }
