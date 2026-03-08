"""
agents/pipeline.py
------------------
Programmatic pipeline runner for the qextract multi-agent system.

This module provides run_pipeline() — the main entry point used by
both the FastAPI server (server.py) and the CLI (main.py).

Instead of using ADK's session/runner infrastructure (which is designed
for interactive chat), this module directly invokes the agents
programmatically for batch processing with parallel page extraction.
"""

from __future__ import annotations

import base64
import json
import os
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

# ── Load .env ────────────────────────────────────────────────────────────────
_project_root = Path(__file__).parent.parent
load_dotenv(dotenv_path=_project_root / ".env", override=False)
load_dotenv(override=False)

from agents.config import MODEL_PROVIDER, load_instruction
from tools.pdf_to_pages import convert_pdf_to_pages
from tools.crop_image import crop_region


# ─────────────────────────────────────────────────────────────────────────────
# LLM CALL HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _call_llm_with_image(instruction: str, page_path: str) -> str:
    """Call the LLM with an image and instruction, return raw text response.

    Supports both OpenAI and Gemini based on MODEL_PROVIDER.
    """
    if MODEL_PROVIDER == "gemini":
        return _call_gemini(instruction, page_path)
    else:
        return _call_openai(instruction, page_path)


def _call_gemini(instruction: str, page_path: str) -> str:
    """Call Gemini with vision via google-genai SDK."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

    # Read image as bytes
    with open(page_path, "rb") as f:
        image_bytes = f.read()

    suffix = Path(page_path).suffix.lower().lstrip(".")
    mime = "image/jpeg" if suffix in ("jpg", "jpeg") else "image/png"

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime),
                    types.Part.from_text(text=f"{instruction}\n\nProcess this exam page image."),
                ],
            )
        ],
        config=types.GenerateContentConfig(
            temperature=0.0,
        ),
    )
    return response.text


def _call_openai(instruction: str, page_path: str) -> str:
    """Call OpenAI GPT-4o-mini with vision via openai SDK."""
    import openai

    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Read image as base64
    with open(page_path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")

    suffix = Path(page_path).suffix.lower().lstrip(".")
    mime = "image/jpeg" if suffix in ("jpg", "jpeg") else "image/png"

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": instruction},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime};base64,{data}",
                            "detail": "high",
                        },
                    },
                    {"type": "text", "text": "Process this exam page image."},
                ],
            },
        ],
        temperature=0.0,
    )
    return response.choices[0].message.content


def _call_llm_text(instruction: str, user_message: str) -> str:
    """Call the LLM with text only (no image), return raw text response."""
    if MODEL_PROVIDER == "gemini":
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=f"{instruction}\n\n{user_message}")],
                )
            ],
            config=types.GenerateContentConfig(temperature=0.0),
        )
        return response.text
    else:
        import openai

        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": instruction},
                {"role": "user", "content": user_message},
            ],
            temperature=0.0,
        )
        return response.choices[0].message.content


# ─────────────────────────────────────────────────────────────────────────────
# JSON PARSING
# ─────────────────────────────────────────────────────────────────────────────

def _parse_json(raw: str) -> list:
    """Strip accidental markdown fences and parse JSON."""
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        inner = lines[1:]
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        raw = "\n".join(inner).strip()
    return json.loads(raw)


# ─────────────────────────────────────────────────────────────────────────────
# PER-PAGE EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

def _extract_text_from_page(page_path: str) -> list[dict]:
    """Run text extraction agent on a single page."""
    instruction = load_instruction("text_extraction.md")
    raw = _call_llm_with_image(instruction, page_path)
    try:
        return _parse_json(raw)
    except json.JSONDecodeError:
        print(f"  ⚠ Text extraction JSON parse failed for {page_path}")
        return []


def _extract_visuals_from_page(page_path: str) -> list[dict]:
    """Run visual detection agent on a single page."""
    instruction = load_instruction("visual_detection.md")
    raw = _call_llm_with_image(instruction, page_path)
    try:
        return _parse_json(raw)
    except json.JSONDecodeError:
        print(f"  ⚠ Visual detection JSON parse failed for {page_path}")
        return []


def _process_single_page(page_path: str, page_num: int) -> dict:
    """Process a single page: extract text + visuals in parallel.

    Args:
        page_path: Path to the page image.
        page_num: 1-based page number.

    Returns:
        dict with keys: page_num, page_path, text_results, visual_results
    """
    print(f"  → Processing page {page_num}: {page_path}")

    # Run text and visual extraction in parallel threads
    with ThreadPoolExecutor(max_workers=2) as executor:
        text_future = executor.submit(_extract_text_from_page, page_path)
        visual_future = executor.submit(_extract_visuals_from_page, page_path)

        text_results = text_future.result()
        visual_results = visual_future.result()

    print(f"     Page {page_num}: {len(text_results)} question(s), "
          f"{len(visual_results)} visual(s)")

    return {
        "page_num": page_num,
        "page_path": page_path,
        "text_results": text_results,
        "visual_results": visual_results,
    }


# ─────────────────────────────────────────────────────────────────────────────
# MERGE + CROP LOGIC
# ─────────────────────────────────────────────────────────────────────────────

def _merge_page_results(page_data: dict) -> list[dict]:
    """Merge text + visual results for one page, crop visuals.

    Returns list of merged question dicts.
    """
    text_results = page_data["text_results"]
    visual_results = page_data["visual_results"]
    page_path = page_data["page_path"]

    # Initialise image fields
    for q in text_results:
        q["QuestionImage"] = None
        for opt in q.get("Options", []):
            opt.setdefault("Image", None)

    # Match visuals to questions and crop
    for v in visual_results:
        q_idx = int(v.get("question_number", 0)) - 1
        if q_idx < 0 or q_idx >= len(text_results):
            continue

        q = text_results[q_idx]
        bbox = v.get("bbox", [])
        if len(bbox) != 4:
            continue

        x_left, y_top, x_right, y_bottom = bbox
        desc = v.get("description", "visual")

        if v.get("belongs_to") == "question":
            crop_result = crop_region(
                page_path=page_path,
                x_left=x_left, y_top=y_top,
                x_right=x_right, y_bottom=y_bottom,
                label=f"q{q_idx + 1}_main",
            )
            if crop_result["status"] == "success":
                q["QuestionImage"] = {
                    "path": crop_result["cropped_path"],
                    "filename": crop_result["filename"],
                    "description": desc,
                }

        elif v.get("belongs_to") == "option":
            label = v.get("option_label") or ""
            for opt in q.get("Options", []):
                if opt.get("OptionLabel") == label:
                    crop_result = crop_region(
                        page_path=page_path,
                        x_left=x_left, y_top=y_top,
                        x_right=x_right, y_bottom=y_bottom,
                        label=f"q{q_idx + 1}_opt{label}",
                    )
                    if crop_result["status"] == "success":
                        opt["Image"] = {
                            "path": crop_result["cropped_path"],
                            "filename": crop_result["filename"],
                            "description": desc,
                        }
                    break

    return text_results


def _handle_cross_page_continuations(all_page_questions: list[list[dict]]) -> list[dict]:
    """Merge partial questions across page boundaries.

    If the last question on page N has is_partial=True and the first
    question on page N+1 looks like a continuation, merge them.
    """
    merged: list[dict] = []

    for page_idx, page_questions in enumerate(all_page_questions):
        if not page_questions:
            continue

        for q_idx, question in enumerate(page_questions):
            is_partial = question.pop("is_partial", False)

            if q_idx == 0 and merged:
                # Check if previous question was partial
                prev = merged[-1]
                prev_partial = prev.pop("_is_partial", False)

                if prev_partial:
                    # Merge: append text
                    if question.get("QuestionText") and prev.get("QuestionText"):
                        prev["QuestionText"] += " " + question["QuestionText"]
                    elif question.get("QuestionText"):
                        prev["QuestionText"] = question["QuestionText"]

                    if question.get("QuestionTextHindi") and prev.get("QuestionTextHindi"):
                        prev["QuestionTextHindi"] += " " + question["QuestionTextHindi"]

                    # If the continuation has options and the partial doesn't
                    if question.get("Options") and not prev.get("Options"):
                        prev["Options"] = question["Options"]
                    elif question.get("Options") and prev.get("Options"):
                        # Merge options (continuation's options supplement)
                        existing_labels = {o["OptionLabel"] for o in prev["Options"]}
                        for opt in question["Options"]:
                            if opt["OptionLabel"] not in existing_labels:
                                prev["Options"].append(opt)

                    # Merge images
                    if question.get("QuestionImage") and not prev.get("QuestionImage"):
                        prev["QuestionImage"] = question["QuestionImage"]

                    continue  # Skip adding as new question

            # Mark if partial for next page check
            if is_partial and q_idx == len(page_questions) - 1:
                question["_is_partial"] = True

            merged.append(question)

    # Clean up internal markers and renumber
    for i, q in enumerate(merged):
        q.pop("_is_partial", None)
        q["question_number"] = i + 1

    return merged


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC — MAIN PIPELINE ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

def run_pipeline(input_path: str) -> tuple[list[dict], dict]:
    """Extract all questions from an exam file (PDF or image).

    This is the main entry point used by server.py and main.py.

    Args:
        input_path: Path to a PDF or image file.

    Returns:
        tuple[list[dict], dict]: (questions, metadata)
            - questions: list of extracted question dicts
            - metadata: dict with page_count, model_provider, etc.

    Raises:
        ValueError: If file type is not supported.
        FileNotFoundError: If input file doesn't exist.
    """
    input_path = str(Path(input_path).resolve())
    ext = Path(input_path).suffix.lower()

    if not Path(input_path).is_file():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if ext not in (".pdf", ".png", ".jpg", ".jpeg"):
        raise ValueError(
            f"Unsupported file type: {ext!r}  "
            f"(accepted: .pdf .png .jpg .jpeg)"
        )

    print(f"\n🚀 qextract pipeline starting...")
    print(f"   Model: {MODEL_PROVIDER.upper()}")
    print(f"   Input: {input_path}\n")

    # ── Step 1: Convert to page images ────────────────────────────────────────
    if ext == ".pdf":
        result = convert_pdf_to_pages(input_path)
        if result["status"] == "error":
            raise RuntimeError(f"PDF conversion failed: {result['error_message']}")
        page_paths = result["page_paths"]
        print(f"   📄 Converted PDF → {len(page_paths)} page(s)\n")
    else:
        page_paths = [input_path]
        print(f"   🖼  Single image input\n")

    # ── Step 2: Process pages in parallel ─────────────────────────────────────
    max_workers = min(len(page_paths), 4)  # Cap at 4 parallel pages
    page_results: list[dict] = [None] * len(page_paths)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for i, page_path in enumerate(page_paths):
            future = executor.submit(_process_single_page, page_path, i + 1)
            futures[future] = i

        for future in as_completed(futures):
            idx = futures[future]
            try:
                page_results[idx] = future.result()
            except Exception as exc:
                print(f"  ⚠ Page {idx + 1} failed: {exc}")
                traceback.print_exc()
                page_results[idx] = {
                    "page_num": idx + 1,
                    "page_path": page_paths[idx],
                    "text_results": [],
                    "visual_results": [],
                }

    # ── Step 3: Merge results per page (crop visuals) ─────────────────────────
    print(f"\n🔗 Merging results and cropping visuals...")
    all_page_questions: list[list[dict]] = []

    for page_data in page_results:
        merged = _merge_page_results(page_data)
        all_page_questions.append(merged)

    # ── Step 4: Handle cross-page continuations ───────────────────────────────
    final_questions = _handle_cross_page_continuations(all_page_questions)

    # ── Build metadata ────────────────────────────────────────────────────────
    total_visuals = sum(
        1 for q in final_questions
        if q.get("QuestionImage") is not None
    )

    metadata = {
        "page_count": len(page_paths),
        "question_count": len(final_questions),
        "visuals_count": total_visuals,
        "model_provider": MODEL_PROVIDER,
    }

    print(f"\n✅ Extraction complete!")
    print(f"   Questions: {metadata['question_count']}")
    print(f"   Visuals:   {metadata['visuals_count']}")
    print(f"   Pages:     {metadata['page_count']}")
    print(f"   Model:     {metadata['model_provider']}")

    return final_questions, metadata
