# Plano — `--imagens` (PDF-only) + avaliação Rust/Go

> Formato: Maestro (thin-planner). PRD graded → grafo de tarefas → evidence-gate por nó.
> Data: 2026-08-04 · Escopo fechado: **somente PDF**.

---

## Parte 1 — Feature `--imagens`

### PRD graded

| Critério | Nota | Justificativa |
|---|---|---|
| Clareza de objetivo | **A** | "Usuário escolhe entre transcrever (OCR) ou preservar as imagens do PDF" — sem ambiguidade |
| Critério de done mensurável | **A** | PDF-fixture com 2 imagens embutidas → 2 PNGs em disco + 2 links `![]()` no MD |
| Escopo fechado | **A** | PDF apenas. DOCX/PPTX/XLSX/imagem-solta **fora**, por decisão explícita |
| Riscos identificados | **B** | Path traversal e zip/resource bomb mapeados; comportamento em PDF-scan ainda é decisão aberta (D3) |

**Verdict: A−** → executável.

### Estado atual (verificado)

- `pdf_to_md()` ([core/converter.py:24](../core/converter.py)) chama `pymupdf4llm.to_markdown()` **sem** `write_images` → toda imagem embutida é descartada.
- `_texto_filtrado_margens()` ignora explicitamente `block["type"] != 0` (type 1 = imagem).
- `_ocr_pagina()` renderiza a página a 300 dpi em `NamedTemporaryFile` e **apaga** o PNG no `finally`.
- `batch.py:131` já tem o precedente de parâmetro PDF-only:
  ```python
  if conversor is pdf_to_md and ignorar_margens > 0:
      return pdf_to_md(origem, ignorar_margens=ignorar_margens)
  ```
  → `--imagens` segue o mesmo padrão. Zero mudança nos outros conversores.

### API

```python
# core/utils.py
class ModoImagem(str, Enum):
    transcrever = "transcrever"  # default — comportamento atual, byte-idêntico
    extrair     = "extrair"      # salva arquivo + ![](assets/...)
    ambos       = "ambos"        # extrai + OCR como alt-text
    ignorar     = "ignorar"      # descarta sem OCR
```

```
pdf2md converter <origem> --imagens transcrever|extrair|ambos|ignorar
                          [--assets-dir <path>]
```

- Default `transcrever` ⇒ **backward-compatible**. Golden MDs existentes não mudam.
- Flag só afeta `.pdf`. Aplicada a outro formato → warning, não erro (mesma semântica de `--ignorar-margens` hoje).

### Decisões travadas

| # | Decisão | Escolha | Motivo |
|---|---|---|---|
| D1 | Destino dos assets | `<stem>_assets/` ao lado do `.md`; `--obsidian` → pasta de attachments do vault + `![[wikilink]]` | Obsidian não resolve `![]()` relativo de forma confiável |
| D2 | Base64 inline | **Não** | +33% no `.md`, quebra render do Obsidian, mata diff |
| D3 | Página-scan (sem texto nativo) | Em `extrair`/`ambos`, persiste o render 300 dpi como `p{n}_full.png` | `get_images()` num scan devolve 1 imagem = a página inteira; persistir o render evita path duplicado |
| D4 | Dedup | SHA-256 dos bytes → 1 arquivo por hash, N links | Logo de rodapé em 200 páginas = 200 PNGs sem isso |
| D5 | Nomenclatura | `img_p{pagina:03d}_{idx}.{ext}` — **sempre gerado**, nunca derivado de metadado do PDF | Mitiga path traversal (ver Segurança) |

### Segurança (gate Sentinel — obrigatório, toca escrita em FS)

- **Path traversal:** nome de imagem embutida vem do documento (atacante). Mitigação D5 + `Path.resolve()` + assert `assets_dir in resolved.parents`.
- **Resource bomb:** PDF com 10k imagens ou 1 imagem de 2 GB. Limites: `_MAX_IMAGENS_PDF = 500`, `_MAX_BYTES_IMAGEM = 50 * 1024 * 1024`. Excedeu → skip + warning, não crash.
- **Symlink:** `assets_dir` existente e symlink → recusa.
- **Path do usuário em stack trace:** `RuntimeError` genérico, igual ao padrão atual de `converter.py`.

### Grafo de tarefas (ordem topológica)

```
T1 ──> T2 ──> T3 ──> T4 ──> T6 ──> T7
        └────> T5 ───┘
```

| # | Tarefa | Agente | Done criterion (Evidence) |
|---|---|---|---|
| **T1** | `ModoImagem` enum + constantes de limite em `core/utils.py` | stratum | `uv run ruff check core/` limpo; import do enum em teste passa |
| **T2** | `core/pdf_images.py` novo: `extrair_imagens(doc, pagina, assets_dir) -> list[AssetImagem]` — dedup SHA-256, limites, sanitização | stratum | `pytest tests/test_pdf_images.py` — 6 casos: normal, dedup, limite excedido, nome hostil, symlink, PDF sem imagem |
| **T3** | `pdf_to_md(..., modo_imagem, assets_dir)` — wire em `_processar_pagina` e `_ocr_pagina` | stratum | Fixture com 2 imagens → 2 PNGs + 2 links; modo default produz MD **byte-idêntico** ao golden atual |
| **T4** | Propagação `cli.py` → `batch.py` (padrão `ignorar_margens`, batch.py:131) | stratum | `pdf2md converter dir/ --imagens extrair` → assets por arquivo, sem colisão de nome sob ThreadPool |
| **T5** | Modo `--obsidian`: wikilink + attachments do vault | stratum | MD contém `![[img_p001_0.png]]` e arquivo existe no vault |
| **T6** | Review de segurança | **sentinel** (veto) | 0 finding crítico; traversal e bomb com teste que prova a mitigação |
| **T7** | Docs: README + CHANGELOG + ADR-0005 | herald | ADR-0005 registra D1–D5 |

**Fora de escopo (PR futuro, não abrir agora):** DOCX/PPTX/XLSX, GUI SwiftUI (picker segmentado), conversão de formato (HEIC→PNG), compressão de asset.

### Regressão obrigatória

`pytest tests/ -v` inteiro verde **antes** de T6. Golden MDs não podem mudar em modo default — se mudarem, T3 está errado, não o golden.

---

## Parte 2 — Rust / Go: avaliação

### Onde o tempo realmente vai

Medido nesta máquina (`uv run python -c "import fitz, pymupdf4llm, PIL, docx, pptx, openpyxl, typer"`, warm):

```
import stack:  0.81 s / 0.84 s   (interpretador vazio: 0.06 s)
```

⇒ **~0.78 s de overhead fixo por invocação**, antes de tocar em qualquer arquivo. Sob PyInstaller one-file é pior (extração do bundle em `_MEIxxxx`).

Decomposição do resto do custo:

| Etapa | Onde executa hoje | Ganho de reescrever em Rust/Go |
|---|---|---|
| Parse do PDF | **MuPDF (C)** via PyMuPDF | ~0 — já é nativo |
| OCR | **Tesseract (C++)**, subprocess | ~0 — já é nativo |
| Decode de imagem | **libjpeg/libpng (C)** via Pillow | ~0 |
| Heurística layout→Markdown | **`pymupdf4llm`, Python puro** | Real, mas é *o* código a reimplementar |
| Orquestração do batch | `ThreadPoolExecutor` (batch.py:266) | Real — ver abaixo |
| Startup do processo | CPython + imports | Real: ~0.78 s → ~5 ms |

### O problema estrutural do batch

`batch.py` usa **ThreadPoolExecutor**, não processos. Consequência sob GIL:
- OCR escala (subprocess → GIL liberado no wait) ✅
- MuPDF escala parcialmente (libera GIL em partes) ⚠️
- `pymupdf4llm` **não escala** — Python puro, serializa no GIL ❌

Num PDF nativo de texto (sem OCR), `--workers 8` rende bem menos que 8×. Esse é o gargalo real, e é o único item da lista onde Rust/Go dá ganho de ordem de grandeza.

### Estado do ecossistema

| Capacidade | Rust | Go |
|---|---|---|
| Parse PDF | `mupdf-rs` / `pdfium-render` / `lopdf` | `go-fitz` (cgo→MuPDF), `pdfcpu`, `unipdf` (**pago**) |
| OCR | `leptess`/`tesseract-rs` (cgo-like), `ocrs` (puro, mais fraco) | `gosseract` (cgo) |
| PDF→Markdown com layout | **Não existe equivalente a `pymupdf4llm`** | **Não existe** |
| xlsx | `calamine` (excelente) | `excelize` (excelente) |
| docx/pptx | `docx-rs` (limitado), pptx ~inexistente | `unioffice` (**pago**) |

O bloqueador é a linha 3. `pymupdf4llm` é ~2k linhas de heurística de layout (detecção de coluna, tabela, header, nível de heading) sem porte em nenhuma das duas linguagens. Reescrever = reimplementar a peça de maior valor e maior risco do produto, com regressão silenciosa de qualidade que os golden tests **não** pegam (MD "parecido" mas pior).

Adicionalmente: `unipdf` e `unioffice` (Go) são comerciais → violam a constraint "sem deps pagas" do [CLAUDE.md](../CLAUDE.md). Restam `pdfcpu`/`go-fitz`, ambos sem camada de markdown.

### Veredito

**Não reescrever `core/` em Rust ou Go.** O trabalho pesado já é C nativo; o Python é cola. O ganho ficaria em startup e paralelismo — e ambos têm solução em Python, mais barata:

| Ganho pretendido | Alternativa Python | Custo |
|---|---|---|
| −0.78 s de startup | Lazy import: mover `docx`/`pptx`/`openpyxl`/`PIL` para dentro das funções (padrão já usado em `image_converter.py`) | ~2 h |
| Paralelismo real | `ProcessPoolExecutor` no batch — mata o GIL. Comentário em `batch.py:3` cita compat PyInstaller; testar `freeze_support()` | ~1 dia |
| Startup ~0 na GUI | Modo daemon: processo Python vivo, GUI fala por socket/stdin | ~2 dias |

**Onde Rust/Go faria sentido no futuro** (nenhum é agora):
1. **Wrapper CLI fino** em Go que faz fan-out de N processos Python — ganha paralelismo sem tocar na conversão. Mas `ProcessPoolExecutor` entrega o mesmo sem linguagem nova.
2. **Extensão pontual via PyO3 (Rust)** se um hotspot específico for medido — ex.: pré-processamento de imagem pré-OCR. Só depois de profiler, não por intuição.
3. **Reescrita da GUI** — irrelevante, SwiftUI já é nativo.

**Pré-requisito para qualquer reconsideração:** profiling real (`py-spy record` num batch de 50 PDFs mistos). Sem número medido, a discussão é especulativa — e ADR-0001 fixou Python+SwiftUI, então mudar exige ADR novo com evidência, não preferência.

### Ação recomendada

- **ADR-0005:** decisões D1–D5 da feature de imagens.
- **ADR-0006:** "Manter Python no core — Rust/Go rejeitado", com os números acima. Registra a decisão para não reabrir a cada ciclo.
- **Backlog separado (não bloqueia `--imagens`):** lazy imports; `py-spy` num batch de 50 PDFs; spike de `ProcessPoolExecutor` sob PyInstaller.

---

## Parte 3 — Seleção de provider + modelo na GUI

### Bug encontrado (motiva a feature)

`llm_enhancer` lê **exclusivamente** env vars ([core/llm_enhancer.py:60](../core/llm_enhancer.py)). `BatchProcessor` cria `Process()` sem definir `.environment` ([gui/PDF2MD/BatchProcessor.swift:130](../gui/PDF2MD/BatchProcessor.swift)) → herda o env do processo pai. Um `.app` aberto pelo Finder **não** herda o env do shell (`~/.zshrc` nunca roda).

Consequência: `PDF2MD_LLM_URL` ausente → `disponivel()` cai no early-return

```python
if url == _URL_PADRAO and "PDF2MD_LLM_URL" not in os.environ:
    return False
```

→ `--llm-fallback` é **no-op silencioso na GUI**. O toggle liga, nada acontece, nenhum aviso. Os dropdowns são a correção, não só cosmética.

### Design

Substituir o `Toggle` solto ([ContentView.swift:83](../gui/PDF2MD/ContentView.swift)) por um bloco que revela dois `Picker` quando ligado:

```
[x] ⚡ Melhorar com IA (fallback)
    Provedor  [ Ollama (local)      ▾ ]   ● conectado
    Modelo    [ llama3.2-vision     ▾ ]   👁 visão
    API key   [ •••••••••• ]  (oculto se provedor = Ollama)
```

**Presets de provider** (struct estática em Swift, espelha o docstring de `llm_enhancer`):

| Provedor | URL base | Key? | Visão |
|---|---|---|---|
| Ollama (local) | `http://localhost:11434/v1` | não | depende do modelo |
| Gemini | `https://generativelanguage.googleapis.com/v1beta/openai/` | sim | sim |
| Groq | `https://api.groq.com/openai/v1` | sim | **não** |
| OpenRouter | `https://openrouter.ai/api/v1` | sim | depende |
| Personalizado… | campo livre | sim | desconhecido |

**Lista de modelos — dinâmica, não hardcoded.** `disponivel()` já bate em `GET {url}/models`; a mesma resposta popula o dropdown. Assim o Ollama do usuário lista os modelos que ele realmente tem instalados. Falhou a chamada → cai numa lista estática mínima por provider + campo editável.

Swift **não** deve reimplementar o HTTP. Novo subcomando:

```
pdf2md llm modelos --json   # → {"modelos":[{"id":"llama3.2-vision","visao":true}, ...]}
pdf2md llm testar  --json   # → {"ok":true,"latencia_ms":142}
```

Reusa `_url()` e sua validação de SSRF. GUI só faz parse do JSON — mesmo padrão do `--json` já usado em `BatchProcessor`.

### Decisões travadas

| # | Decisão | Escolha | Motivo |
|---|---|---|---|
| D6 | Onde persiste provider/modelo | `@AppStorage` (UserDefaults) | Não é segredo |
| D7 | Onde persiste a API key | **Keychain** (`kSecClassGenericPassword`, service `com.pdf2md.llm`) | UserDefaults é plist em claro dentro do container do app |
| D8 | Como a key chega no Python | `processo.environment` (dict explícito), **nunca em argv** | argv aparece em `ps aux` para qualquer processo do mesmo usuário |
| D9 | Modelo sem visão + OCR fallback | Aviso inline no picker ("Groq não tem visão — OCR de imagem fica só no Tesseract") | Evita expectativa quebrada silenciosa |
| D10 | Sem provider configurado | Toggle **desabilitado** com dica "Configure um provedor" | Melhor que ligar e não fazer nada (bug atual) |

### Segurança (gate Sentinel)

- **Key em argv:** proibido (D8). Verificar que nenhum `args.append` toca na key.
- **Key em log:** `BatchProcessor` captura stdout do processo — garantir que `--json` nunca ecoa a key. `melhorar_markdown` já suprime `str(exc)` por CWE-209/532; manter no subcomando novo.
- **URL personalizada = SSRF por design:** `_url()` já aplica allowlist `http/https` e rejeita userinfo. Não adicionar bloqueio de IP privado — `localhost` é o caso de uso principal (Ollama). A URL vem do usuário, não de um documento; risco aceito, registrar no ADR.
- **Entitlements:** `.app` sandboxed precisa de `com.apple.security.network.client` para alcançar o endpoint. Verificar em `scripts/build_app.sh`.
- **Keychain:** o binário precisa estar assinado de forma estável, senão o macOS invalida o item de Keychain a cada rebuild.

### Grafo de tarefas

```
T8 ──> T9 ──> T10 ──> T11 ──> T13
        └────> T12 ──┘
```

| # | Tarefa | Agente | Done criterion (Evidence) |
|---|---|---|---|
| **T8** | CLI: flags `--llm-url` / `--llm-modelo`, precedência flag > env > default; refatorar `_url`/`_modelo` | stratum | `pytest tests/test_llm_enhancer.py` — precedência coberta; env-only continua funcionando |
| **T9** | Subcomandos `pdf2md llm modelos --json` e `llm testar --json` | stratum | Contra Ollama local: lista modelos instalados; sem servidor: `{"ok":false}` com exit 0, não traceback |
| **T10** | Swift: `LLMProvider` enum com presets + `LLMConfig` `@AppStorage` | facet | Trocar provider atualiza URL e limpa o modelo selecionado |
| **T11** | Swift: dois `Picker` + campo de key + indicador de status; popula via T9 | facet | Ollama rodando → dropdown mostra os modelos reais; parado → estático + aviso |
| **T12** | Swift: helper de Keychain (`salvar`/`ler`/`apagar` key) | facet | Key sobrevive a restart do app; ausente do `UserDefaults` (verificar com `defaults read`) |
| **T13** | `BatchProcessor`: injeta `PDF2MD_LLM_*` em `processo.environment` | facet + **sentinel** | Toggle ligado converte de fato com LLM; `ps aux` durante a conversão não mostra a key |

**Fora de escopo:** streaming de resposta, seleção de modelo por arquivo, contador de custo/token, gerenciamento de múltiplos perfis.

### Relação com a Parte 1

Independente — nenhuma dependência entre `--imagens` e os dropdowns. **PR separado** (`feat/llm-picker`). Não misturar: a Parte 3 toca GUI + Keychain + assinatura, superfície de review diferente.

---

## Sequência de execução

```
PR 1 — feat/imagens-pdf
T1 → T2 → T3 → T4 → T5 → T6 (sentinel, veto) → T7 (docs+ADRs)

PR 2 — feat/llm-picker  (independente, pode ir em paralelo)
T8 → T9 → T10 → T11 → T13 (sentinel, veto)
             └─> T12 ──┘
```

---

## Parte 4 — `pdf-inspector` (Firecrawl): correção da Parte 2

### O que invalida a Parte 2

A Parte 2 concluiu "não existe equivalente a `pymupdf4llm` em Rust". **Falso.** Firecrawl lançou o [Fire-PDF](https://www.firecrawl.dev/blog/fire-pdf-launch) (14/04/2026) e open-sourceou o núcleo como [`pdf-inspector`](https://github.com/firecrawl/pdf-inspector) — Rust puro, **MIT**, com binding Python publicado no PyPI.

Distinção que importa:

| Componente | Natureza | Serve? |
|---|---|---|
| **Fire-PDF** (pipeline completo: layout neural + GLM-OCR) | **API hospedada, paga** | ❌ Viola "sem deps pagas" ([CLAUDE.md](../CLAUDE.md)) e exige upload de documento — inaceitável p/ material jurídico/pessoal |
| **`pdf-inspector`** (classificação + extração + markdown) | **MIT, local, offline** | ✅ Candidato direto |

### Verificação executada (2026-08-04, este Mac)

Instalação limpa em venv descartável: `pdf-inspector 0.2.6`, wheel `cp38-abi3-macosx_11_0_arm64` — **instala sem toolchain Rust**, ABI estável, sem build.

Bake-off em `2607.29626v1.pdf` (arXiv, 69 páginas, 2 colunas, muitas tabelas):

| Engine | Wall time | Chars MD | Linhas de tabela |
|---|---|---|---|
| `pdf-inspector.process_pdf` | **0,17 s** | 187.724 | 1.586 |
| `pymupdf4llm.to_markdown` | 49,13 s | 189.224 | 1.656 |
| `core.converter.pdf_to_md` (atual) | 59,90 s | 189.153 | — |

**~290× mais rápido** que `pymupdf4llm`, **~350×** que o pipeline atual. Volume de conteúdo e extração de tabela equivalentes.

Achado colateral: `pymupdf4llm` **disparou Tesseract sozinho** em 3 páginas (`OCR on page.number=0/1…`) num PDF que o `pdf-inspector` classifica como `text_based` com `pages_needing_ocr = []`. Parte dos 49 s é OCR desperdiçado num PDF de texto nativo.

**Qualidade não é uniformemente melhor.** No bloco de título/autores o `pdf-inspector` saiu pior — `###` espúrio em nome de autor, superscrito virando `*,*3*,*4`. Tabelas ficaram equivalentes. ⇒ **Ganho de velocidade é comprovado; ganho de qualidade não é.**

### Encaixe na arquitetura

`extract_pages_markdown(path, pages=None)` devolve `PageMarkdown` por página com `.markdown`, `.needs_ocr`, `.ocr_reason`. É **a mesma forma** de `_extrair_chunks_markdown` + `_processar_pagina` ([core/converter.py](../core/converter.py)) — substituição estrutural, não reescrita.

Bônus: `needs_ocr` substitui a heurística `_MIN_TEXTO_PAGINA = 50`, que hoje decide OCR contando caracteres. O classificador olha os internos do PDF.

**PyMuPDF permanece obrigatório**, não sai da stack:
- render 300 dpi das páginas de scan (`_ocr_pagina`)
- extração das imagens embutidas da **Parte 1**
- `pdf-inspector` **não faz OCR** — o caminho Tesseract fica intacto

Ou seja: `pdf-inspector` troca só a camada texto-nativo→markdown. Não toca em OCR nem em imagem.

### Riscos

- **Maturidade:** 0.1.0 em 12/03/2026, 0.2.6 em 31/07/2026. <5 meses, pré-1.0. API pode quebrar.
- **Parser diferente:** usa `lopdf`, não MuPDF. Modos de falha distintos em PDFs exóticos/corrompidos — exatamente onde MuPDF é forte.
- **Corpus enviesado:** o benchmark próprio da Firecrawl (0,875 vs 0,735) é dele, no corpus dele. Meu teste é **1 paper acadêmico**. O corpus real do usuário é jurídico, contábil, apostila FIAP e scan — perfil diferente.
- **Vendor:** projeto de empresa comercial cujo produto principal é a API paga. O MIT pode não ser mantido com o mesmo empenho.

### Tarefa

| # | Tarefa | Agente | Done criterion (Evidence) |
|---|---|---|---|
| **T14** | Bake-off em corpus real: ≥20 PDFs do usuário (jurídico, contábil, apostila, scan). Comparar MD lado a lado + tempo. Não usar arXiv nem o benchmark da Firecrawl | neuron | Tabela por documento: tempo, chars, tabelas, defeito qualitativo. Veredito por categoria |
| **T15** | Se T14 aprovar: `--parser mupdf\|inspector` (default `mupdf`), `pdf-inspector` opcional em `[project.optional-dependencies]` | stratum | Golden tests passam nos dois parsers; ausência do pacote não quebra import |
| **T16** | Trocar `_MIN_TEXTO_PAGINA` por `needs_ocr` quando parser = inspector | stratum | Página de scan continua indo para OCR; página de texto nativo para de disparar OCR à toa |

**Não trocar o default agora.** `mupdf` continua padrão até T14 provar paridade de qualidade no corpus real. Velocidade sem paridade é regressão disfarçada.

### Efeito na Parte 2

`ProcessPoolExecutor` provavelmente deixa de ser necessário: extensão Rust libera o GIL, então o `ThreadPoolExecutor` atual ([batch.py:266](../core/batch.py)) passa a escalar de verdade no caminho texto-nativo — que era exatamente o gargalo diagnosticado. Reavaliar **depois** de T15, não antes.

**ADR-0006 precisa de emenda:** a premissa "sem equivalente em Rust" está errada. Veredito revisado: *não reescrever `core/` em Rust/Go — mas adotar biblioteca Rust madura via binding Python onde a medição justificar.* Continua sem trocar de linguagem; muda a dependência.

---

## Parte 5 — Layout da GUI ✅ FEITO

### Pedido

"O quadro onde aparecem os arquivos a converter deve ser triplicado."

### Primeira tentativa — descartada

Teto da lista 160 → 480 (3×), `minHeight` da janela 420 → 640. **Reprovado no teste visual:** com 22 arquivos, a lista de 480 empurrava campo de saída, toggles e o botão Converter para fora da janela. Converter exigia rolagem — pior que os 160 originais. Subir `minHeight` além de 640 não resolve: não cabe em MacBook 13".

### Solução aplicada — lista elástica

- **`ScrollView` externo removido.** Era ele que travava tudo na altura intrínseca e impedia qualquer expansão. A `List` já rola sozinha.
- Lista: `minHeight: 160, maxHeight: .infinity`. Piso de ~5 linhas, **sem teto** — cresce com a janela.
- **Rodapé ancorado** (caminho, toggles, Converter) fora da área elástica: nunca sai da tela, independente da quantidade de arquivos.
- **Zona de drop adaptativa:** 280pt sem arquivos (absorve o espaço vazio e amplia o alvo de drop), 110pt com arquivos.
- `minHeight` da janela: 420 → 640.

### Evidence

Build via `swiftc` + `.app` de preview com lista semeada (22 arquivos), inspecionado em tela:

| Cenário | Resultado |
|---|---|
| Janela grande | 22 arquivos visíveis de uma vez; Converter ancorado e visível |
| Janela no mínimo | Lista encolhe para ~8 linhas; Converter continua visível e clicável |
| Lista vazia | Zona de drop ocupa o espaço; zero área morta |

Type-check `swiftc` limpo. Arquivo tocado: [gui/PDF2MD/ContentView.swift](../gui/PDF2MD/ContentView.swift). **Não commitado.**

### Consequência para a Parte 3 (⚠️ novo)

O rodapé agora é **ancorado e de altura fixa**. Os dois `Picker` + campo de API key da T11 entram exatamente nele, somando ~90pt. Com `minHeight: 640` o rodapé passa a consumir mais da metade da janela mínima e espreme a lista contra o piso de 160.

Mitigação a decidir na T11 — pegar uma:
- Revelar os pickers só com o toggle ligado (já era o design) **e** subir `minHeight` para ~700; ou
- Mover a config de LLM para uma janela de Preferências (`Settings` scene), tirando-a do rodapé por completo.

**Recomendado:** Preferências. O provider/modelo é config de uma vez, não decisão por conversão — não merece espaço permanente na janela principal.

### Débito não tratado

"pdf2md" aparece duas vezes — barra de título da janela e cabeçalho interno ([ContentView.swift:61](../gui/PDF2MD/ContentView.swift)). ~40pt verticais em redundância. Fora do escopo do pedido; candidato à T11.

---

## Parte 6 — `anydoc` (Firecrawl): DOCX/PPTX/XLSX

[`firecrawl/anydoc`](https://github.com/firecrawl/anydoc) — Rust puro, **MIT**, binding Python (`pip install firecrawl-anydoc`, módulo `anydoc`). Converte docx/doc/odt/rtf/epub/pptx/ppt/xlsx/ods/odp/csv/pdf → GFM. Usa `pdf-inspector` internamente para PDF. Local, offline, sem modelo de ML.

Testado aqui: **v0.1.3**, instalada e executada contra fixtures geradas.

### Correção da Parte 1 ❗

A Parte 1 afirma que DOCX/PPTX/XLSX "descartam imagem, texto só". **Errado para DOCX.** `doc_to_md()` (mammoth) já embute a imagem como **data-URI base64** no Markdown.

Saída real do `core/doc_converter.py` para um .docx com uma imagem:

```
![](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAzsAAASSCAIAAAAZ...)
```

Ou seja: o comportamento hoje é **inconsistente entre formatos** — PDF descarta a imagem, DOCX embute base64. E o base64, rejeitado na decisão **D2**, já é o padrão de fato para DOCX. A feature `--imagens` precisa unificar isso, não só adicionar um modo ao PDF.

### Medições (fixtures geradas localmente)

| Formato | anydoc | pdf2md atual | Fator |
|---|---|---|---|
| `.docx` (heading, lista, tabela 3×3, imagem) | **0,012 s** | 2,497 s | ~200× |
| `.pptx` (título, bullets, imagem) | **0,004 s** | 0,331 s | ~80× |
| `.xlsx` (3 linhas, acentos) | **0,001 s** | 0,233 s | ~200× |

### Qualidade — nenhum é estritamente superior

**Onde `anydoc` ganha:**
- **Tabela DOCX:** `doc_to_md` emite `c00`, `c01`, `c02` como parágrafos soltos — não vira tabela. `anydoc` emite tabela GFM correta.
- **Bullets PPTX:** `pptx_to_md` emite parágrafos soltos; `anydoc` emite lista `-`.
- Sem escape agressivo (mammoth produz `três\.`).

**Onde o pdf2md atual ganha:**
- **Nome da aba XLSX** (`## Dados`) — `anydoc` descarta.
- **Número do slide PPTX** (`## Slide 1`) — `anydoc` descarta. Perda de contexto de navegação.
- `anydoc` colapsou heading nível 0 e nível 1 do DOCX ambos em `#` — hierarquia perdida.
- `anydoc.to_markdown` emite o nome do arquivo de imagem como **texto solto** (`img_teste.png`) em vez de `![]()`.

**Bug encontrado de passagem** (independente, chip aberto): [core/xlsx_converter.py:84](../core/xlsx_converter.py) usa `"\n\n".join(partes)` misturando heading com linhas da tabela → linha em branco entre cada linha → **a tabela não renderiza no Obsidian**. A função de CSV logo abaixo já faz certo com `"\n".join`.

### O que isto resolve na Parte 1

`to_document(bytes)` devolve `Document` com:
- `assets: list[Asset]` — cada um com `data: bytes`, `media_type`, `origin_part`
- blocos com `Inline(kind="image")` **na posição correta** do documento

Verificado: no .docx de teste, o bloco 6 é `paragraph` com inline `image`, entre "Antes da imagem:" e "Depois da imagem." — posição preservada.

Isso elimina o item que a Parte 1 classificou como custo "médio" (*"DOCX: posição é o difícil"*). Se a feature de imagens for estendida para DOCX/PPTX, `anydoc` entrega posição + bytes prontos.

⚠️ `origin_part` (`word/media/image1.png`) **não pode** virar nome de arquivo — é string controlada pelo documento. Vale a decisão **D5**: nome sempre gerado.

### Riscos

- **v0.1.3.** Mais novo e menos maduro que o `pdf-inspector` (0.2.6). Muito pré-1.0.
- **Regressão de metadado** é certa, não hipotética: nome de aba e número de slide somem. Para material de estudo (apostila, planilha) isso importa.
- Mesmo vendor, mesma dependência estratégica da Parte 4.

### Tarefas

| # | Tarefa | Agente | Done criterion (Evidence) |
|---|---|---|---|
| **T17** | Bake-off em documentos reais do usuário (≥10 docx/pptx/xlsx: apostila, planilha de estudo, slide de aula). Não usar fixture sintética | neuron | Tabela por documento com defeito qualitativo nomeado; veredito por formato |
| **T18** | Se T17 aprovar: `anydoc` como parser opcional por formato, preservando nome de aba e número de slide (envolver, não substituir cru) | stratum | Golden tests passam; metadado preservado; ausência do pacote não quebra import |
| **T19** | Unificar política de imagem entre formatos — DOCX para de embutir base64 por padrão e passa a respeitar `--imagens` | stratum | Mesmo `--imagens` produz comportamento equivalente em PDF e DOCX |

**T19 é o mais importante desta parte** e não depende do `anydoc`: é corrigir a inconsistência que já existe hoje.

### Efeito no plano

- **Parte 1:** o inventário "DOCX/PPTX/XLSX descartam imagem" está errado — corrigido acima. T19 entra no escopo da feature de imagens.
- **Parte 4:** `anydoc` usa `pdf-inspector` internamente. Se T15 e T18 forem ambos aprovados, `anydoc` sozinho cobre os dois casos — avaliar adotar só ele em vez de duas dependências.

---

## Sequência revisada

ADRs: **0005** imagens (D1–D5) · **0006** Rust/Go rejeitado + emenda `pdf-inspector` · **0007** config de LLM (D6–D10).

| Ordem | PR | Tarefas | Bloqueio |
|---|---|---|---|
| **0** | `fix/layout-lista` | Parte 5 | ✅ pronto — só falta commit |
| **1** | `feat/llm-picker` | T8–T13 | nenhum. T8/T9 são CLI, testáveis sem Xcode. Corrige feature que hoje **não funciona** no `.app` |
| **2** | `feat/imagens-pdf` | T1–T7 | aval das decisões D1–D5 |
| **3** | `feat/parser-inspector` | T14–T16 | precisa de ~20 PDFs reais do usuário. Sem corpus, T14 não vale nada |
| **4** | `feat/parser-anydoc` | T17–T19 | T17/T18 precisam de docs reais. **T19 não depende de nada** — pode subir junto com o PR 2 |

Justificativa da ordem: PR 1 antes do PR 2 porque bug > feature nova — o toggle de IA existe na UI e é no-op silencioso hoje. PR 3 por último porque é o único que depende de insumo externo.

Os três são independentes entre si; a ordem é de prioridade, não de dependência.

Regressão `pytest tests/ -v` verde antes de cada gate sentinel. PR para `main` em todos os casos — sem push direto ([CLAUDE.md](../CLAUDE.md)).
