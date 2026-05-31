# Changelog

Based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [SemVer](https://semver.org/).

## [0.4.0] — 2026-05-30

### Added

- **New formats**: `.pptx` (python-pptx — slides, titles, tables), `.xlsx`
  (openpyxl — sheets → MD tables), `.csv` (stdlib — BOM/UTF-8/Latin-1).
- **Automatic quality pipeline**: every conversion runs
  `corrigir_mojibake` (22 PT-BR patterns), `limpar_artefatos` (U+00AD soft hyphen,
  zero-width chars, mid-string BOM, non-breaking space) and `validar_qualidade`
  (residual mojibake, U+FFFD, short output). Warnings ⚠ in CLI and GUI.
- **LLM fallback** (`--llm-fallback` / `--llm`): uses a local LLM (Ollama) or remote
  to improve quality on problematic conversions. Provider-agnostic via
  OpenAI-compatible API (urllib stdlib — zero extra deps). Defaults to
  Ollama `http://localhost:11434/v1`; supports Gemini, Groq, OpenRouter via env vars.
- **GUI — Browse files**: button opens multi-select NSOpenPanel with all supported types.
- **GUI — Paste image**: pastes image from clipboard directly into queue; saves
  as temp PNG with UUID filename (no per-second collision).
- **GUI — ⚡ AI Enhance toggle**: passes `--llm-fallback` to the Python binary.
- `docs/Standards-Anti-Patterns.md`: technical catalog of 8 patterns/anti-patterns
  (subprocess-PATH in PyInstaller, hdiutil DMG, ThreadPoolExecutor, defensive decode,
  native fd1 vs sys.stdout, stem collision, traversal, containment by layer).
- `tasks/lessons.md`: 24 lessons from Cycles 1–6 propagated from vault to repo.

### Fixed (max-effort code review — 13 findings)

- `sobrescrever=False` returned `CONCLUIDO` for skipped files due to name collision;
  now returns `IGNORADO` (distinguishable from actual conversion).
- `alertaColar: Bool` replaced by `erroColagem: String?` — distinct messages
  for empty clipboard vs I/O error; re-triggers on consecutive failures.
- `limpar()` now deletes temporary paste PNG files before removing URLs.
- Paste filename uses `UUID().uuidString` (no per-second collision).
- `guard let cachesBase` replaces `first!` (force-unwrap eliminated).
- Removed `.keyboardShortcut("v")` from Paste button — no longer intercepts
  Cmd+V in future text fields.
- `NSApp.activate(ignoringOtherApps: true)` before `runModal()` — picker
  appears in front in multi-window scenarios (macOS 14+).
- `tiposPermitidos` promoted to `static let` with canonical UTIs for `.doc`/`.docx`
  (works without Microsoft Office installed); computed once.
- `adicionarSeNovo()` centralizes dedup — `handleDrop`, `adicionarArquivos`
  and `colarImagem` all call it.
- `ProgressoArquivo.avisos: [String]` added with custom Codable init
  (backward compat with older binaries that didn't emit the field).

### Notes

- Build Apple Silicon (arm64), macOS 13+.
- New PPTX/XLSX/CSV formats require no external tools — pure Python.
- LLM fallback requires `PDF2MD_LLM_URL` to be set; without it the feature
  stays inactive even if the toggle is on (graceful degradation).

## [0.3.1] — 2026-05-29

### Fixed
- **Per-file time always showed "0.0s"**: text conversions take milliseconds and
  the `.1f` formatter rounded everything below 0.05s to "0.0s". Sub-second
  durations now display in ms (e.g. `15ms`, `216ms`). Affects CLI and GUI.
  The measurement was always correct — only the display truncated it.

## [0.3.0] — 2026-05-29

### Added
- **Conversion timing**: per-file duration and total time. CLI shows a "Time"
  column in the results table, `TimeElapsedColumn` in the progress bar, and
  total time in the summary. GUI shows per-item time in the list, "Done in Xs"
  message, and duration in the notification.

### Fixed
- **antiword not found** in packaged app (`.doc`): PyInstaller's minimal PATH
  doesn't include `/opt/homebrew/bin/`, so `subprocess` couldn't find antiword
  even when installed. Explicit path resolution added, mirroring the Tesseract fix.
- **Polluted stdout in `--json` mode**: MuPDF (via pymupdf4llm) writes messages
  to native fd 1 ("Using Tesseract for OCR processing") which contaminated the
  Swift bridge JSON protocol. Now redirected to stderr around the conversion,
  keeping stdout clean.

## [0.2.0] — 2026-05-29

### Added
- Word document support: `.docx` via mammoth, `.doc` via antiword.
- **Cancel** button in GUI with cooperative process cancellation.
- **Unified path field** (same selector for output folder and Obsidian vault).
- App icon (AppIcon).
- `scripts/build_app.sh` — reproducible `.app` + `.dmg` build (PyInstaller +
  swiftc + ad-hoc codesign + hdiutil), no hardcoded paths.

### Fixed
- Tesseract not found in PyInstaller binary (minimal PATH on macOS).
- **Data loss**: files with the same base name but different extensions
  (`report.pdf` + `report.docx`) collided on the same `.md` under `ThreadPoolExecutor`.
- **GUI deadlock**: reading pipe after `waitUntilExit()` with stderr never
  drained could freeze the app.
- `.doc` files with PT-BR accents broke (antiword emits Latin-1; decode was UTF-8).
- Cancelling left the UI without a reset button; reconverting during teardown
  created a state race.
- Tesseract gate blocked Word-only conversions (which don't use OCR).
- O(n) PDF re-parse per page → now single-pass `page_chunks`.
- OCR re-validated Tesseract per page (subprocess) → memoized.
- Path traversal detection by component (`path.parts`); error messages no longer
  leak the user's absolute path.
- `.doc` dispatched by magic bytes (`PK`→mammoth, OLE→antiword).

### Notes
- Build **Apple Silicon (arm64)**, macOS 13+. OCR requires Tesseract:
  `brew install tesseract tesseract-lang`.
- App is ad-hoc signed: on first launch, right-click → **Open**
  (Gatekeeper bypass).

## [0.1.0] — 2026-05-29

- Initial release: PDF and images → Markdown, OCR via Tesseract, Obsidian
  integration (YAML frontmatter + output to vault root).
