# Changelog

All notable changes to qextract are documented here.

## [2.0.0] — 2026-03-08

### 🔄 Complete Redesign — Google ADK Multi-Agent System

#### Added
- **Multi-agent architecture** using Google ADK (Agent Development Kit)
- **Dual model support**: OpenAI GPT-4o-mini and Google Gemini 2.0 Flash
- `agents/` package with 4 specialized agents:
  - `OrchestratorAgent` — root coordinator
  - `PageTextAgent` — OCR + text extraction
  - `PageVisualAgent` — visual element detection with bounding boxes
  - `MergerAgent` — merge text + visuals, handle cross-page continuations
- `instructions/` directory with separate prompt files (`.md`)
- `tools/` package with ADK-compatible tool functions
- **Parallel processing**: pages processed concurrently
- **Cross-page question continuation** handling
- `pipeline.py` — programmatic runner for server/CLI
- `ARCHITECTURE.md` — system architecture documentation
- `CHANGELOG.md` — version history
- `README.md` — comprehensive project documentation

#### Changed
- Server now returns `metadata` object instead of `cost` field
- UI updated to display model provider and handle new image object format
- `requirements.txt` updated with `google-adk`, `google-genai`, `litellm`

#### Removed
- Old `qextract/` package (replaced by `agents/`, `tools/`, `instructions/`)
- Direct OpenAI-only API call pattern

---

## [1.0.0] — 2026-03-07

### Initial Release
- Two-pass extraction (text + visuals) using OpenAI `gpt-4o-mini`
- FastAPI server with debug UI
- CLI entry point
- Image cropping with normalized bounding boxes
- PDF to PNG conversion
