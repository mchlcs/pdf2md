# pdf2md

Convert PDFs, images, Word, PPTX and spreadsheets to Markdown — batch processing, Obsidian vault integration, and LLM-powered quality fallback.

![CI](https://github.com/phant0um/pdf2md/actions/workflows/ci.yml/badge.svg)

## Supported formats

| Format | Conversion |
|--------|-----------|
| `.pdf` | Native text extraction + automatic OCR for scanned pages |
| `.docx` | mammoth — preserves headings, bold, lists, tables |
| `.doc` | textutil (native macOS — no extra install needed) |
| `.pptx` | python-pptx — slides, titles, tables |
| `.xlsx` | openpyxl — each sheet becomes a Markdown table |
| `.csv` | stdlib — BOM, UTF-8, Latin-1 support |
| `.png` `.jpg` `.jpeg` `.tiff` `.webp` `.bmp` `.heic` | OCR via Tesseract |

## Requirement — Tesseract OCR

Required for scanned PDFs and images containing text.

```bash
brew install tesseract tesseract-lang
```

> `tesseract-lang` includes Portuguese support (`por`). Required for PT-BR documents.

## macOS App (GUI)

1. Download `PDF2MD-vX.X.X.dmg` from [Releases](https://github.com/phant0um/pdf2md/releases)
2. Drag **PDF2MD.app** to Applications
3. **First launch:** right-click → Open (Gatekeeper bypass — app is ad-hoc signed)
4. Install Tesseract (step above)

### Adding files

Three ways to add files for conversion:
- **Drag and drop** files or folders onto the drop zone
- **Browse files…** — opens a multi-format file picker
- **Paste image** — pastes an image from the clipboard directly into the queue (screenshots, browser copies)

### Obsidian mode

Enable the **Obsidian Mode** toggle to:
- Add automatic YAML frontmatter to each generated MD
- Save directly to the vault root (select the vault root folder)

```yaml
---
title: filename
source: original.pdf
converted: 2026-05-30
tags:
  - pdf2md
  - converted
---
```

### ⚡ AI Enhance (fallback)

Enable the **AI Enhance** toggle to use an LLM when conversion detects quality issues (broken words, corrupted encoding, very short output).

Configure the provider in the app's **Settings** window (pdf2md → Settings…): provider, model and API key. The model list is fetched live from the provider; if it's unreachable, a static list is shown. The API key is stored in the **macOS Keychain**, never in plain settings.

Providers: Ollama (local), Gemini, Groq, OpenRouter, or a custom OpenAI-compatible URL.

```bash
brew install ollama
ollama pull llama3.2-vision
```

The CLI equivalent uses environment variables — see CLI section below.

## CLI

```bash
# Install
pip3 install "pdf2md[dev]"  # or: uv sync

# Convert single file
pdf2md file.pdf output/
pdf2md presentation.pptx output/
pdf2md spreadsheet.xlsx output/

# Convert entire folder (parallel)
pdf2md docs/ output/ --workers 8

# With Obsidian frontmatter
pdf2md file.pdf output/ --obsidian

# Directly to vault
pdf2md docs/ --vault ~/Obsidian/my-vault

# LLM fallback: improves quality when issues are detected
export PDF2MD_LLM_URL=http://localhost:11434/v1   # Ollama (free, local)
pdf2md scanned.pdf output/ --llm-fallback

# Flags override env vars (flag > env > default)
pdf2md docs/ output/ --llm-fallback --llm-url https://api.groq.com/openai/v1 --llm-modelo llama-3.1-8b-instant

# LLM always (regardless of quality)
pdf2md docs/ output/ --llm

# Ignore page headers and footers (5% of page height from top and bottom)
pdf2md document.pdf output/ --ignorar-margens 5

# Diagnose the LLM endpoint (used by the GUI picker)
pdf2md llm modelos --json    # → {"ok":true,"modelos":[{"id":"...","visao":true}]}
pdf2md llm testar --json     # → {"ok":true,"latencia_ms":42}
```

### LLM configuration

Precedence: `--llm-url` / `--llm-modelo` flags > env vars > defaults. The API key always comes from `PDF2MD_LLM_KEY` (or the GUI's Keychain) — never from a flag.

| Provider | PDF2MD_LLM_URL | PDF2MD_LLM_MODEL |
|----------|----------------|------------------|
| Ollama (local, free) | `http://localhost:11434/v1` | `llama3.2-vision` |
| Gemini Flash (free tier) | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-2.0-flash` |
| Groq (fast, free) | `https://api.groq.com/openai/v1` | `llama-3.1-8b-instant` |

## Quality pipeline

Every conversion runs through an automatic pipeline:

1. **Mojibake correction** — fixes corrupted accents (`Ã£`→`ã`, `Ã§`→`ç` etc.)
2. **Artifact cleanup** — removes soft hyphens (U+00AD), zero-width chars, mid-string BOM
3. **Validation** — detects residual issues and shows ⚠ warnings in CLI and GUI

Files with quality issues show an amber icon (✓ orange) in the GUI and `done⚠` status in the CLI.

## Development

```bash
git clone https://github.com/phant0um/pdf2md
cd pdf2md
uv sync --extra dev
uv run pytest tests/ -v
uv run ruff check core/ tests/
```

## Stack

| Component | Technology |
|-----------|-----------|
| PDF → MD | `pymupdf4llm` + `PyMuPDF` |
| OCR | `tesseract` + `pytesseract` |
| Images | `Pillow` + `pillow-heif` (HEIC) |
| DOCX | `mammoth` |
| DOC | `textutil` (native macOS) |
| PPTX | `python-pptx` |
| XLSX | `openpyxl` |
| LLM fallback | OpenAI-compatible (Ollama/Gemini/Groq) via urllib |
| CLI | `typer` + `rich` |
| GUI | SwiftUI (macOS 13+) |
| CI | GitHub Actions |

## License

Source code: **MIT** — see [LICENSE](LICENSE).

The distributed binary (`.dmg`) bundles **PyMuPDF** (AGPL-3.0) and other third-party libraries. Distribution of the binary is subject to the terms of those licenses — see [THIRD-PARTY-LICENSES.md](THIRD-PARTY-LICENSES.md). The corresponding source is public (this repository), satisfying the AGPL.
