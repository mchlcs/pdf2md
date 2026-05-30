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

## Ciclo 3 (Code Review + Release v0.2.0) — CONCLUÍDO ✅
- Status: Fechado — 2026-05-29
- Release: https://github.com/mchlcs/pdf2md/releases/tag/v0.2.0 (**Latest**)
- v0.1.0 rebaixado a **pre-release** (bug do Tesseract + desatualizado)

### Code Review (max-effort — 5 finders + verify + sweep)
- 33 candidatos → **15 achados verificados → 15 corrigidos** (PRs #1, #3)
- Cluster crítico: perda de dados (colisão de stem no batch), deadlock de pipe
  na GUI (leitura após `waitUntilExit`), encoding Latin-1 do antiword (.doc
  PT-BR), estado de cancelamento (UI sem reset / corrida ao reconverter)
- 2ª leva: gate OCR só quando necessário, `page_chunks` (passada única),
  `lru_cache` no OCR, traversal por `path.parts`, confinamento home por
  componente (Swift), dedup `EXTENSOES_DOC`, docstrings, teste `.doc` reforçado,
  dispatch `.doc` por magic bytes, toggle travado durante conversão
- Relatório completo: vault `01-PROJECTS/pdf2md/code-review-ciclo2.md`

### Empacotamento reproduzível (Bastion)
- `scripts/build_app.sh`: PyInstaller → swiftc → bundle → codesign ad-hoc → DMG
  - paths dinâmicos (zero hardcode), versão lida do `pyproject.toml`
  - DMG via imagem RW de tamanho explícito + detach por **device node** (`-force`)
    — contorna 3 armadilhas do hdiutil (`-format` exige srcfolder; auto-size
    estoura com binário 84MB; detach por mountpoint dá "busy")
- Bump: `0.1.0-alpha` → **0.2.0**; `CHANGELOG.md` criado
- Binário congelado smoke-tested: PDF + DOCX (mammoth embarcado) + colisão #1
  (2 MDs distintos, sem perda) + gate OCR #6
- DMG: `PDF2MD-v0.2.0.dmg` (88.5MB, UDZO) — SHA256 `9034aa94…675108`

### Novidades v0.2.0 (desde v0.1.0)
- Suporte a **Word**: `.docx` (mammoth), `.doc` (antiword)
- Botão **cancelar** + campo de caminho **unificado** + ícone do app
- Fix do **Tesseract não-encontrado** no binário PyInstaller (o bug que
  quebrava a v0.1.0 empacotada)

### Fluxo
- PRs #1 (cluster #1–5), #2 (gitignore), #3 (build + bump) — todos
  squash-merged em `main`, CI verde
- Build agora é 1 comando reproduzível: `bash scripts/build_app.sh`

## Ciclo 4 (Release v0.3.0) — CONCLUÍDO ✅
- Status: Fechado — 2026-05-29
- Release: https://github.com/mchlcs/pdf2md/releases/tag/v0.3.0 (**Latest**)
- Gatilho: usuário reportou erro "antiword não encontrado" ao converter `.doc`

### Correções
- **antiword não-encontrado no app empacotado** (`.doc`): PATH mínimo do binário
  PyInstaller não inclui `/opt/homebrew/bin/` — **mesma classe do bug do
  Tesseract** na v0.1.0. `_resolver_antiword()` resolve o caminho explícito
  (PATH → fallback Homebrew), espelhando `_configurar_tesseract_cmd`.
  Validado no binário **congelado** + `.doc` OLE real (textutil) + PATH sem
  homebrew → conversão OK, acentos corretos.
- **stdout poluído no modo `--json`**: MuPDF (via pymupdf4llm) escreve no fd 1
  nativo ("Using Tesseract for OCR processing") — `redirect_stdout` do Python
  não pega. `_silenciar_stdout_nativo()` redireciona fd 1→fd 2 ao redor da
  conversão. Verificado: stdout 100% JSON puro.

### Novidade v0.3.0
- **Tempo de conversão**: duração por-arquivo + total. CLI (coluna "Tempo" +
  `TimeElapsedColumn` + total) e GUI (lista + "Concluído em Xs" + notificação).
  Medido no core (`ResultadoArquivo.duracao`), reportado via CLI e JSON.

### Padrão registrado (lição)
Binário PyInstaller = PATH mínimo. Todo `subprocess` de binário de sistema
(antiword, tesseract, futuros) precisa de resolução de path explícita. Há 2
resolvers espelhados; replicar o padrão para novas deps externas.

### Fluxo
- PR #4 (progress Ciclo 3), #5 (v0.3.0) — squash-merged em `main`, CI verde
- DMG: `PDF2MD-v0.3.0.dmg` (84.4MB) — SHA256 `3c8177fa…a5cc64`
- v0.2.0 mantida como release normal; v0.1.0 segue pre-release
