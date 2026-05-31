# Changelog

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).
Versionamento [SemVer](https://semver.org/lang/pt-BR/).

## [0.4.0] — 2026-05-30

### Adicionado

- **Novos formatos**: `.pptx` (python-pptx — slides, títulos, tabelas), `.xlsx`
  (openpyxl — sheets → tabelas MD), `.csv` (stdlib — BOM/UTF-8/Latin-1).
- **Pipeline de qualidade automático**: todas as conversões passam por
  `corrigir_mojibake` (22 padrões PT-BR), `limpar_artefatos` (U+00AD soft hyphen,
  zero-width chars, BOM mid-string, non-breaking space) e `validar_qualidade`
  (mojibake residual, U+FFFD, output curto). Avisos ⚠ no CLI e GUI.
- **LLM fallback** (`--llm-fallback` / `--llm`): usa LLM local (Ollama) ou remoto
  para melhorar qualidade de conversões problemáticas. Provider-agnostic via
  API compatível com OpenAI (urllib stdlib — zero deps extras). Defaults para
  Ollama `http://localhost:11434/v1`; suporta Gemini, Groq, OpenRouter via env vars.
- **GUI — Procurar arquivos**: botão abre NSOpenPanel multi-select com todos os
  tipos suportados.
- **GUI — Colar imagem**: cola imagem do clipboard diretamente na fila; salva
  como PNG temporário com nome UUID (sem colisão por segundo).
- **GUI — Toggle ⚡ Melhorar com IA**: ativa `--llm-fallback` para conversões
  com qualidade baixa.
- `docs/Standards-Anti-Patterns.md`: catálogo técnico de 8 padrões/anti-padrões
  (subprocess-PATH em PyInstaller, hdiutil, ThreadPoolExecutor, decode defensivo,
  fd1 nativo, colisão de stem, traversal, confinamento por camada).
- `tasks/lessons.md`: 24 lições dos Ciclos 1–6 propagadas do vault para o repo.

### Corrigido (code review max-effort — 13 findings)

- `sobrescrever=False` retornava `CONCLUIDO` para arquivos pulados por colisão;
  agora retorna `IGNORADO` (distinguível de conversão real).
- `alertaColar: Bool` substituído por `erroColagem: String?` — mensagens
  distintas para clipboard vazio vs erro de I/O; re-trigger em falhas consecutivas.
- `limpar()` agora deleta arquivos PNG temporários de paste antes de remover URLs.
- Nome de arquivo paste usa `UUID().uuidString` (sem colisão por segundo).
- `guard let cachesBase` substitui `first!` (eliminado force-unwrap).
- Removido `.keyboardShortcut("v")` do botão Colar — não intercepta mais Cmd+V
  de text fields futuros.
- `NSApp.activate(ignoringOtherApps: true)` antes de `runModal()` — picker
  aparece na frente em cenários multi-janela (macOS 14+).
- `tiposPermitidos` promovido a `static let` com UTI canônicas para `.doc`/`.docx`
  (funciona sem Microsoft Office instalado); construído uma única vez.
- `adicionarSeNovo()` centraliza dedup de arquivo — `handleDrop`, `adicionarArquivos`
  e `colarImagem` chamam só ela.
- `ProgressoArquivo.avisos: [String]` adicionado com Codable custom init
  (backward compat com binários antigos que não emitiam o campo).

### Notas

- Build Apple Silicon (arm64), macOS 13+.
- Novos formatos PPTX/XLSX/CSV não requerem ferramentas externas — puras Python.
- LLM fallback requer `PDF2MD_LLM_URL` definido; sem a variável, feature fica
  desativada mesmo se toggle ligado (graceful degradation).

## [0.3.1] — 2026-05-29

### Corrigido
- **Tempo por-arquivo aparecia sempre "0.0s"**: conversões de texto levam
  milissegundos e o formatador `.1f` arredondava tudo abaixo de 0.05s para
  "0.0s". Sub-segundo agora é exibido em ms (ex: `15ms`, `216ms`). Afeta CLI e
  GUI. A medição sempre esteve correta — só o display truncava.

## [0.3.0] — 2026-05-29

### Adicionado
- **Tempo de conversão**: duração por-arquivo e total. No CLI, coluna "Tempo" na
  tabela + `TimeElapsedColumn` na barra + tempo total no resumo. Na GUI, tempo
  por item na lista + "Concluído em Xs" + duração na notificação.

### Corrigido
- **antiword não encontrado** no app empacotado (`.doc`): o PATH mínimo do
  binário PyInstaller não inclui `/opt/homebrew/bin/`, então o `subprocess` não
  achava o antiword mesmo instalado. Resolução explícita do caminho, espelhando
  o fix do Tesseract.
- **stdout poluído no modo `--json`**: o MuPDF (via pymupdf4llm) escreve
  mensagens nativas no fd 1 ("Using Tesseract for OCR processing") que
  contaminavam o protocolo JSON do bridge Swift. Agora redirecionadas para o
  stderr ao redor da conversão, mantendo o stdout puro.

## [0.2.0] — 2026-05-29

### Adicionado
- Suporte a documentos Word: `.docx` via mammoth, `.doc` via antiword.
- Botão **Cancelar** na GUI com cancelamento cooperativo do processo.
- Campo de caminho **unificado** (mesma seleção para pasta de saída e vault Obsidian).
- Ícone do app (AppIcon).
- `scripts/build_app.sh` — build reproduzível `.app` + `.dmg` (PyInstaller +
  swiftc + codesign ad-hoc + hdiutil), sem paths hardcoded.

### Corrigido
- Tesseract não era encontrado no binário PyInstaller (PATH mínimo no macOS).
- **Perda de dados**: arquivos de mesmo nome-base com extensões diferentes
  (`report.pdf` + `report.docx`) colidiam no mesmo `.md` sob `ThreadPoolExecutor`.
- **Deadlock da GUI**: leitura de pipe após `waitUntilExit()` + `stderr` nunca
  drenado podia congelar o app.
- `.doc` PT-BR com acentos quebrava (antiword emite Latin-1; decode era UTF-8).
- Cancelar deixava a UI sem botão de reset; reconverter durante o teardown
  criava corrida de estado.
- Gate de Tesseract bloqueava conversão **só de Word** (que não usa OCR).
- Reparse O(n) do PDF por página → agora `page_chunks` em passada única.
- OCR revalidava Tesseract por página (subprocess) → memoizado.
- Validação de path traversal por componente (`path.parts`); mensagens de erro
  não vazam mais o path absoluto do usuário.
- `.doc` despachado por magic bytes (`PK`→mammoth, OLE→antiword).

### Notas
- Build **Apple Silicon (arm64)**, macOS 13+. OCR requer Tesseract:
  `brew install tesseract tesseract-lang`.
- App com assinatura ad-hoc: na primeira execução, clique-direito → **Abrir**
  (bypass do Gatekeeper).

## [0.1.0] — 2026-05-29

- Release inicial: PDF e imagens → Markdown, OCR via Tesseract, integração
  Obsidian (frontmatter YAML + saída em `_inbox/`).
