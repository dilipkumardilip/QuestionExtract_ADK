"""
agents/pipeline.py
------------------
Programmatic single-agent pipeline runner for qextract.

This module provides run_pipeline() — the main entry point used by
both the FastAPI server (server.py) and the CLI (main.py).

It makes exactly ONE LLM call per page to extract both text and visual
bounding boxes simultaneously, then crops the images and assembles the final JSON.
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
# SINGLE PASS PAGE EXTRACTION & CROPPING
# ─────────────────────────────────────────────────────────────────────────────

def _process_single_page(page_path: str, page_num: int) -> list[dict]:
    """Process a single page: extract text and visuals in ONE LLM call, then crop.

    Args:
        page_path: Path to the page image.
        page_num: 1-based page number.

    Returns:
        List of finalized question dicts for this page.
    """
    print(f"  → Processing page {page_num}: {page_path}")

    # 1. LLM Extraction (Text + Visual Bboxes via unified prompt)
    instruction = load_instruction("extraction.md")
    raw_response = _call_llm_with_image(instruction, page_path)
    
    try:
        questions = _parse_json(raw_response)
    except json.JSONDecodeError:
        print(f"  ⚠ JSON parse failed for {page_path}")
        return []

    # 2. Process and Crop Visuals directly from the JSON
    for q_idx, q in enumerate(questions):
        q["QuestionImage"] = None
        
        # Crop main question visual if bbox exists
        q_bbox = q.pop("QuestionVisualBbox", None)
        q_desc = q.pop("QuestionVisualDesc", "visual")
        
        if isinstance(q_bbox, list) and len(q_bbox) == 4:
            x_left, y_top, x_right, y_bottom = q_bbox
            crop_res = crop_region(
                page_path=page_path,
                x_left=x_left, y_top=y_top, x_right=x_right, y_bottom=y_bottom,
                label=f"q{q.get('printed_number', q_idx + 1)}_main"
            )
            if crop_res["status"] == "success":
                q["QuestionImage"] = {
                    "path": crop_res["cropped_path"],
                    "filename": crop_res["filename"],
                    "description": q_desc
                }
                
        # Crop option visuals if bbox exists
        for opt in q.get("Options", []):
            opt["Image"] = None
            opt_bbox = opt.pop("VisualBbox", None)
            opt_desc = opt.pop("VisualDesc", "option visual")
            
            if isinstance(opt_bbox, list) and len(opt_bbox) == 4:
                olabel = opt.get("OptionLabel", "")
                x_left, y_top, x_right, y_bottom = opt_bbox
                crop_res = crop_region(
                    page_path=page_path,
                    x_left=x_left, y_top=y_top, x_right=x_right, y_bottom=y_bottom,
                    label=f"q{q.get('printed_number', q_idx + 1)}_opt{olabel}"
                )
                if crop_res["status"] == "success":
                    opt["Image"] = {
                        "path": crop_res["cropped_path"],
                        "filename": crop_res["filename"],
                        "description": opt_desc
                    }

    print(f"     Page {page_num}: Extracted {len(questions)} question(s).")
    return questions


# ─────────────────────────────────────────────────────────────────────────────
# CROSS-PAGE CONTINUATION PROCESSING
# ─────────────────────────────────────────────────────────────────────────────

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

    Returns:
        tuple[list[dict], dict]: (questions, metadata)
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

    print(f"\n🚀 qextract Single-Agent pipeline starting...")
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
    all_page_questions: list[list[dict]] = [[] for _ in range(len(page_paths))]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for i, page_path in enumerate(page_paths):
            future = executor.submit(_process_single_page, page_path, i + 1)
            futures[future] = i

        for future in as_completed(futures):
            idx = futures[future]
            try:
                all_page_questions[idx] = future.result()
            except Exception as exc:
                print(f"  ⚠ Page {idx + 1} failed: {exc}")
                traceback.print_exc()

    # ── Step 3: Handle cross-page continuations ───────────────────────────────
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
