"""
main.py
-------
CLI entry point for the qextract multi-agent extraction pipeline.

Usage
-----
    python main.py --input exam_paper.pdf
    python main.py --input page1.png --output results.json

Arguments
---------
  --input  / -i   (required)  Path to a PDF or image file (.pdf, .png, .jpg, .jpeg)
  --output / -o   (optional)  Path for the output JSON file (default: results.json)
"""

import argparse
import json
import sys
from pathlib import Path

from agents.pipeline import run_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="qextract",
        description="Extract questions from scanned exam papers "
                    "using a multi-agent system (Google ADK).",
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        metavar="FILE",
        help="Path to the input PDF or image file.",
    )
    parser.add_argument(
        "--output", "-o",
        default="results.json",
        metavar="FILE",
        help="Path for the output JSON file (default: results.json).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    input_path = args.input
    output_path = args.output

    # ── Basic input validation ────────────────────────────────────────────────
    if not Path(input_path).is_file():
        print(f"[ERROR] Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Input:  {input_path}")
    print(f"Output: {output_path}")
    print()

    # ── Run pipeline ──────────────────────────────────────────────────────────
    try:
        questions, metadata = run_pipeline(input_path)
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)
    except EnvironmentError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)

    output_data = {
        "metadata": metadata,
        "questions": questions,
    }

    # ── Write output JSON ─────────────────────────────────────────────────────
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n📁 Output saved to: {output_path}")

    if questions:
        print("\n── First question preview ──────────────────────────────────────")
        print(json.dumps(questions[0], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
