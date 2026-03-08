# qextract — Exam Question Extractor

> Multi-agent system powered by **Google ADK** for extracting questions from scanned Indian competitive exam papers (UPSC, JEE, NEET, SSC, GATE, CAT, RRB).

## ✨ Features

- **Multi-Agent Architecture**: Uses Google ADK with specialized agents for text extraction, visual detection, and result merging
- **Dual Model Support**: Works with both **OpenAI GPT-4o-mini** and **Google Gemini 2.0 Flash**
- **Parallel Processing**: Pages are processed concurrently for faster extraction
- **Visual Element Detection**: Detects and crops diagrams, figures, charts, graphs, maps, shapes, and equation images
- **Cross-Page Handling**: Handles questions that continue across page boundaries
- **Hindi Support**: Extracts Hindi text when present
- **Web UI + CLI + API**: Debug UI, command-line interface, and REST API

## 📦 Project Structure

```
ADK-QExtract/
├── agents/                    # Google ADK agent definitions
│   ├── __init__.py           # Exports root_agent, run_pipeline
│   ├── config.py             # Dual-model config (OpenAI/Gemini)
│   ├── orchestrator_agent.py # Root agent for ADK web UI
│   ├── page_text_agent.py    # Text extraction agent
│   ├── page_visual_agent.py  # Visual detection agent
│   ├── merger_agent.py       # Merge + crop agent
│   └── pipeline.py           # Programmatic pipeline runner
├── instructions/              # Agent instruction prompts
│   ├── text_extraction.md    # OCR + text extraction prompt
│   ├── visual_detection.md   # Visual element detection prompt
│   └── merger.md             # Merge + continuation prompt
├── tools/                     # ADK tool functions
│   ├── __init__.py
│   ├── pdf_to_pages.py       # PDF → PNG conversion
│   └── crop_image.py         # Bbox image cropping
├── server.py                  # FastAPI server
├── main.py                    # CLI entry point
├── ui.html                    # Debug web UI
├── requirements.txt           # Python dependencies
├── .env                       # API keys + model config
├── ARCHITECTURE.md            # System architecture docs
└── CHANGELOG.md               # Version history
```

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# macOS: install poppler for PDF support
brew install poppler

# Create virtual environment
python3 -m venv env_adk_extract
source env_adk_extract/bin/activate

# Install Python packages
pip install -r requirements.txt
```

### 2. Configure API Keys

Edit `.env`:

```env
# Choose your model provider: "openai" or "gemini"
MODEL_PROVIDER=openai

# OpenAI (required if MODEL_PROVIDER=openai)
OPENAI_API_KEY=your_openai_key_here

# Gemini (required if MODEL_PROVIDER=gemini)
# GOOGLE_API_KEY=your_gemini_key_here
```

### 3. Run

**Web UI (recommended):**
```bash
uvicorn server:app --reload --port 8001
# Open http://127.0.0.1:8001
```

**CLI:**
```bash
python main.py --input exam_paper.pdf --output results.json
```

**ADK Dev UI:**
```bash
adk web
# Navigate to the qextract_orchestrator agent
```

## 🔧 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/extract` | Upload exam paper, returns extracted JSON |
| `GET` | `/results/{job_id}` | Fetch cached result |
| `GET` | `/image/{filename}` | Serve cropped image |
| `GET` | `/health` | Health check with model info |
| `GET` | `/` | Debug web UI |

## 📄 Output Format

```json
{
  "job_id": "abc123",
  "filename": "exam.pdf",
  "page_count": 2,
  "metadata": {
    "question_count": 8,
    "visuals_count": 2,
    "model_provider": "openai"
  },
  "questions": [
    {
      "question_number": 1,
      "QuestionText": "Which of the following...",
      "QuestionTextHindi": null,
      "QuestionImage": {
        "path": "/path/to/crop.png",
        "filename": "crop_q1_main_abc123.png",
        "description": "circuit diagram"
      },
      "Options": [
        {"OptionLabel": "A", "Text": "Option text", "Image": null},
        {"OptionLabel": "B", "Text": "Option text", "Image": null}
      ]
    }
  ]
}
```

## 📋 Version

**v2.0.0** — Multi-agent system redesign using Google ADK
