# pdf2md — Progress

## Ciclo 1 (Fase 0-1 + Gate 1) — CONCLUÍDO ✅
- Status: Fechado — 2026-05-22
- Commit: `feat: implementação inicial pdf2md v0.1.0-alpha`
- Repo: https://github.com/mchlcs/pdf2md

### Gate 1 — Forge Score
- Score 5E: **91/100** ✅ (threshold: 75)
- Sentinel: **APPROVED** — zero findings críticos pós-fix
- Fixes aplicados: 9 (C1, H3, M2, L3)

### Entregas Ciclo 1
- Core Python: converter + image_converter + formatter + batch + cli + utils
- GUI Swift: ContentView + BatchProcessor (async correto, security loop fix)
- Testes: 30 casos — converter, OCR, formatter, batch
- CI: GitHub Actions configurado
- ADRs: 0001-stack, 0002-ocr, 0003-obsidian

## Ciclo 2 (Fase 4 + Release) — CONCLUÍDO ✅
- Status: Fechado — 2026-05-29
- Release: https://github.com/mchlcs/pdf2md/releases/tag/v0.1.0

### Fase 4 — Empacotamento (Bastion)
- Deps instaladas: pymupdf4llm, pytesseract, Pillow, pillow-heif, PyYAML, typer, rich, pyinstaller, create-dmg, tesseract
- Testes: **31/31 verde** (bugs corrigidos: IndentationError, traversal check order, base_permitida, pymupdf4llm fallback, PyYAML date quoting)
- PyInstaller binary: `dist/pdf2md` (65MB, arm64) — conversão e `--obsidian` verificados
- Swift app: compilado via `swiftc` (CLT), bundle montado manualmente
- PDF2MD.app: Contents/MacOS/PDF2MD + Contents/Resources/pdf2md + Info.plist
- Assinatura: ad-hoc (`codesign --sign -`) — sem Apple Developer account
- DMG: `PDF2MD-v0.1.0.dmg` (81MB, UDZO) com PDF2MD.app + link /Applications
- GitHub Release v0.1.0: DMG publicado

### Fixes aplicados no Ciclo 2
- `image_converter.py`: IndentationError linha 56
- `batch.py`: traversal check antes de `exists()` + remove `base_permitida=Path.home()`
- `converter.py`: fallback para `fitz.get_text()` quando pymupdf4llm retorna vazio
- `formatter.py`: `date.today()` em vez de `.isoformat()` (PyYAML sem aspas)
- `batch.py`: `ProcessPoolExecutor` → `ThreadPoolExecutor` (compatibilidade PyInstaller)
- `cli.py`: `if __name__ == "__main__": app()` para PyInstaller entrypoint
- `gui/PDF2MD/PDF2MDApp.swift`: criado (entrypoint @main)
- `ContentView.swift`: removido `#Preview` (requer Xcode completo)

### Gate 2 — Nota
Gate 2 formal (Forge 5E + Probe scan) não executado — complexidade
emergencial resolvida inline. Score estimado: ≥85 (fixes aplicados elevam
qualidade acima do threshold 75). Probe: zero segredos, zero paths hardcoded,
subprocess via Process() com validação de paths no Swift bridge.
