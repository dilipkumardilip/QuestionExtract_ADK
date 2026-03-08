# Architecture — qextract Multi-Agent System

## Overview

qextract uses a **multi-agent architecture** built on **Google ADK** (Agent Development Kit) to extract questions from scanned Indian competitive exam papers. The system decomposes the extraction task into specialized sub-tasks handled by different agents.

## Agent Hierarchy

```
OrchestratorAgent (root)
├── PageTextAgent        — OCR + text extraction per page
├── PageVisualAgent      — Visual element detection per page
└── MergerAgent          — Merge results + crop images
```

## Processing Pipeline

```
Input (PDF/Image)
       │
       ▼
┌─────────────────┐
│ PDF → Pages     │  tools/pdf_to_pages.py
│ (pdf2image)     │
└────────┬────────┘
         │
         ▼
┌──────────────────────────────────────┐
│     Parallel Per-Page Processing     │
│  ┌────────────┐  ┌────────────────┐  │
│  │ Text Agent │  │ Visual Agent   │  │  × N pages
│  │ (OCR)      │  │ (bbox detect)  │  │
│  └────────────┘  └────────────────┘  │
└──────────────────┬───────────────────┘
                   │
                   ▼
          ┌────────────────┐
          │  Merge + Crop  │  tools/crop_image.py
          │  Cross-page    │
          │  continuations │
          └────────┬───────┘
                   │
                   ▼
            Final JSON Output
```

## Dual Model Support

| Provider | Model | Config |
|----------|-------|--------|
| OpenAI | `gpt-4o-mini` | `MODEL_PROVIDER=openai` + `OPENAI_API_KEY` |
| Google | `gemini-2.0-flash` | `MODEL_PROVIDER=gemini` + `GOOGLE_API_KEY` |

OpenAI models are connected via **LiteLLM** wrapper. Gemini uses native ADK integration.

## Key Design Decisions

1. **Parallel text + visual extraction**: Each page's text and visual detection run in parallel threads (2 API calls per page, running simultaneously)
2. **Pages processed concurrently**: Multiple pages are processed in parallel (up to 4 at a time) via `ThreadPoolExecutor`
3. **Cross-page continuations**: The merger detects `is_partial: true` on the last question of a page and merges it with the first question of the next page
4. **Normalized bounding boxes**: All coordinates are 0.0–1.0 normalized, making them resolution-independent
5. **Separate instruction files**: Agent prompts live in `instructions/` as standalone `.md` files for easy editing without code changes

## Directory Layout

```
agents/config.py           — Model selection, .env loading, instruction loader
agents/pipeline.py         — Main pipeline: parallel extraction, merge, crop
agents/orchestrator_agent.py — Root agent for ADK web UI
agents/page_text_agent.py  — Text extraction agent factory
agents/page_visual_agent.py — Visual detection agent factory
agents/merger_agent.py     — Merge agent factory with crop tool

tools/pdf_to_pages.py      — PDF → PNG pages (pdf2image)
tools/crop_image.py        — Normalized bbox → cropped PNG (Pillow)

instructions/text_extraction.md   — OCR prompt
instructions/visual_detection.md  — Visual detection prompt
instructions/merger.md            — Merge + continuation prompt
```

## Version

**v2.0.0** — Google ADK multi-agent system
