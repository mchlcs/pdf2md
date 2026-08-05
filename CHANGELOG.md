# Changelog

Based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [SemVer](https://semver.org/).

## [Unreleased]

### Added

- **`--imagens transcrever|extrair|ambos|ignorar`** (PDF-only): política de
  imagens embutidas. `extrair` salva os assets (default `<stem>_assets/`) e
  linka `![](...)`; `ambos` extrai e usa OCR como alt-text; `ignorar`
  descarta sem OCR; default `transcrever` é byte-idêntico ao atual.
  `--assets-dir` sobrescreve o diretório; `--obsidian` usa
  `vault/attachments/` com wikilinks `![[...]]`.
- **Segurança de extração** (ADR-0005): nomes sempre gerados (nunca do
  metadado do PDF), dedup por SHA-256, limites anti resource-bomb (500
  imagens/documento, 50 MB/imagem), recusa de symlink no assets dir, ext
  exótica normalizada para PNG.
- **`core/pdf_images.py`** com 8 testes (extração, dedup, limites, nome
  hostil, symlink, PDF sem imagem).
- **ADR-0005**: decisões D1–D5 (destino, base64 rejeitado, render de scan,
  dedup, nomenclatura).
- **LLM provider/model picker in the GUI (Settings window)** — fixes the
  silent no-op of the AI Enhance toggle in the `.app`: `BatchProcessor` now
  injects `PDF2MD_LLM_URL/MODEL/KEY` into the process environment. Provider
  presets (Ollama, Gemini, Groq, OpenRouter, custom), live model list and
  connection status come from the new `pdf2md llm` subcommands; the API key
  is stored in the macOS Keychain (never in argv — `ps aux` safe).
- **CLI flags `--llm-url` / `--llm-modelo`** with precedence flag > env >
  default, propagated `cli → batch → quality → llm_enhancer` via `ConfigLLM`.
- **`pdf2md llm modelos --json`** — lists models from the endpoint, with
  vision capability detection for local Ollama (`/api/show`).
- **`pdf2md llm testar --json`** — uncached connectivity probe with latency
  measurement; failure returns `{"ok": false}` with exit 0 (JSON is the GUI
  contract, no traceback).
- **ADR-0007**: LLM config decisions D6–D10 (Keychain, env injection, SSRF
  by design, keychain/ad-hoc signing limitation).

### Security

- Error messages from `llm modelos`/`llm testar` are sanitized (CWE-209/532):
  only HTTP code or failure category is exposed, never URL/path/credential.
- API key is transmitted only via `process.environment` (D8) and the
  Authorization header — never through argv or JSON output.
- Image extraction hardening (ADR-0005): path traversal, symlink and
  resource-bomb mitigations with tests proving each one.

## [0.5.0] — 2026-06-29

### Added

- **`--ignorar-margens N`**: Removes page headers and footers from PDF output.
  Filters text blocks by vertical bbox position — N% of page height ignored
  from top and bottom. Default: 0 (disabled).
  Example: `pdf2md doc.pdf output/ --ignorar-margens 5`

### Removed

- **Per-file duration tracking**: `ResultadoArquivo.duracao` field removed.
  Only total conversion time is displayed in CLI output. The JSON output
  no longer includes the `duracao` field per file. GUI Swift updated to
  remove per-file time display.

### Changed

- **Forge 5E score lift (84→90+ projected)**: 12-item action plan implemented:
  - DRY: `_validar_existencia`, `_validar_extensao`, `_sanitizar_celula_md` in utils.py
  - Split: `pdf_to_md`, `_processar_arquivo`, `batch_convert`, `pptx_to_md` into sub-functions <20 lines
  - Magic numbers named: `_MIN_TEXTO_PAGINA`, `_OCR_DPI`, `_MAX_CHARS_LLM`, `_MIN_LARGURA_OCR`, etc.
  - Eficiência: compiled regex for mojibake detection (1 pass vs 24 `str.count`)
  - Eficiência: `_csv_para_md` reads bytes once, decodes in-memory (1 I/O vs 4)
  - Efetividade: lazy import `llm_enhancer` in `aplicar_pipeline_qualidade` (reduces coupling)

## [0.4.2] — 2026-06-29

### Security

- **Username leak fix (CWE-209)**: `sanitizar_mensagem_erro` now redacts
  `/Users/<username>` paths (exactly 2 segments) to `[user]` instead of
  exposing the basename — prevents leaking another user's name in shared
  volumes. Covers usernames with spaces (e.g. `/Users/John Doe` → `[user]`).

### Changed

- **Converter registry**: replaced 5-branch `if/elif` dispatch in
  `_processar_arquivo` with a `_CONVERSORES` registry list. Adding a new
  format is now a one-line change instead of editing the dispatch chain.
- **Quality pipeline extracted**: `aplicar_pipeline_qualidade` in
  `quality.py` now encapsulates the mojibake → cleanup → validate → LLM
  chain. Makes the pipeline unit-testable without a full batch conversion.
- **DRY: extension constants consolidated.** `EXTENSOES_IMAGEM`,
  `EXTENSOES_PPTX`, and `EXTENSOES_PLANILHA` now live only in `utils.py`
  (single source of truth). Converter modules import from there instead
  of redefining duplicated frozensets.
- **Dead code removed**:
  - Unreachable `for/else` branch in `_csv_para_md` (`latin-1` decode
    never fails, so the `else: raise RuntimeError` was unreachable).
  - `_decodificar_textutil` cascade simplified to single
    `decode("utf-8", errors="replace")` — `cp1252`/`latin-1` branches were
    dead code since textutil always emits UTF-8.
  - `validar_extensao` removed (never called in production or tests).
- **Invisible Unicode chars → explicit escapes**: `quality.py` now uses
  `\u00ad`, `\u200b`, `\u200c`, `\u200d`, `\ufeff`, `\u00a0`, `\ufffd`
  instead of invisible literal characters — diff-safe and reviewer-obvious.
- **README + LICENSE + SECURITY.md updated**: corrected GitHub URLs
  (`mchlcs` → `phant0um`), `.doc` conversion description (`antiword` →
  `textutil`), copyright holder, security advisory URL.

## [0.4.1] — 2026-06-29

### Security

- **SSRF hardening (CWE-918)**: `PDF2MD_LLM_URL` now validates scheme
  (`http`/`https` only), rejects embedded credentials, and requires a
  non-empty host before the LLM enhancer makes any request.
- **Error message path leak (CWE-209)**: `sanitizar_mensagem_erro` redacts
  absolute paths in error messages via regex, replacing them with the
  basename or a home-relative `~/...` form — covers symlink-resolved paths
  (e.g. macOS `/var` → `/private/var`), case-insensitive filesystem
  mismatches, and usernames containing spaces (default macOS "First Last").
- Removed raw exception detail from LLM enhancer warnings (no longer leaks
  internal exception text to CLI/GUI output).

### Changed

- **`.doc` (legacy Word) conversion: antiword → textutil.** The `antiword`
  Homebrew formula was disabled upstream (`repo_removed`, 2024), breaking CI.
  Replaced with `textutil` (native macOS CLI, always at `/usr/bin/textutil`,
  no Homebrew dependency, no PyInstaller PATH-resolution hack needed).
  `.docx` conversion via mammoth is unchanged.

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
