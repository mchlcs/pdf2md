# Plano — PR 4: `feat/parser-anydoc` (T17–T18)

> Formato: Maestro (thin-planner). Sequência revisada do plano-imagens-pdf.
> Data: 2026-08-05 · **T19 concluído e mergeado** (unificação de imagens DOCX).
> Estado: **BLOQUEADO no corpus real** — T17 exige ≥10 documentos do usuário.

---

## Contexto

`firecrawl/anydoc` — Rust puro, MIT, binding Python (`pip install
firecrawl-anydoc`, módulo `anydoc`). Converte docx/doc/odt/rtf/epub/pptx/
ppt/xlsx/ods/odp/csv → GFM local, offline. Usa `pdf-inspector` para PDF.
Medições da Parte 6 (fixtures sintéticas): docx ~200×, pptx ~80×, xlsx
~200× mais rápido que o pipeline atual; qualidade NÃO é uniformemente
superior (anydoc perde nome de aba XLSX, número de slide PPTX, hierarquia
de heading DOCX).

**Spike re-executado hoje (2026-08-05):** `uv run --with firecrawl-anydoc
python -c "import anydoc"` → instala sem toolchain Rust, módulo importa
limpo. API confirmada: `Asset, Block, Cell, ConvertError, Document, Format,
ImageSource, Inline, LinkTarget, List, ListItem`.

---

## Grafo

```
T17 (corpus real) ──aprova──> T18 ──> review sentinel ──> PR para main
      └──reprova──> arquiva (documenta veredito no ADR)
```

| # | Tarefa | Agente | Done criterion (Evidence) |
|---|---|---|---|
| **T17** | Bake-off em ≥10 documentos REAIS do usuário (apostila, planilha de estudo, slide de aula; ≥3 por formato) | neuron | Tabela por documento: tempo, chars, tabelas, **defeito qualitativo nomeado**. Veredito por formato (docx/pptx/xlsx). Sem fixture sintética (proibido pelo plano) |
| **T18** | `anydoc` como parser opcional por formato, **envolvendo** (não substituindo cru): metadado preservado | stratum | Golden tests passam nos dois modos; ausência do pacote não quebra import; nome de aba e número de slide preservados |

## Bloqueio (insumo do usuário)

T17 precisa de **corpus real**: ≥10 arquivos (≥3 docx, ≥3 pptx, ≥3 xlsx) —
apostila FIAP, planilha de estudo, slides de aula. Sem o corpus, o gate
de aprovação não pode ser avaliado; rodar com fixture sintética viola o
plano (corpus enviesado) e o veredito não vale nada.

**Formato de entrega:** copiar para `~/Dev/projetos/pdf2md/auditoria-corpus/`
(ou informar o path) — os arquivos NUNCA entram no git (jurídico/pessoal).

## T18 — esboço de implementação (quando T17 aprovar)

1. **Dependência opcional** em `pyproject.toml`:
   ```toml
   [project.optional-dependencies]
   anydoc = ["firecrawl-anydoc>=0.1.3"]
   ```
   Import SEMPRE com guard (`try/except ImportError`) no módulo do
   conversor — padrão já usado no doc_converter com mammoth.
2. **Dispatch por formato** em `batch.py` (estender `_CONVERSORES`): manter
   os conversores atuais como default; `--parser anydoc` seleciona o novo
   caminho só para docx/pptx/xlsx (pdf-inspector interno do anydoc fica
   FORA — PR 3 decide o parser de PDF separadamente).
3. **Preservar metadado (não substituir cru):**
   - XLSX: `anydoc.to_markdown` perde o nome da aba → envolver: usar o
     resultado do anydoc e re-injetar `## <aba>` por tabela (via
     `anydoc.to_document` + blocos por part/aba, se exposto) — ou manter
     `openpyxl` para o cabeçalho e anydoc para o corpo.
   - PPTX: re-injetar `## Slide N` por bloco de slide.
   - DOCX: re-mapear heading nível 0/1 → `#`/`##` (anydoc colapsa em `#`).
4. **Imagens:** anydoc devolve `Asset` com `data`/`media_type`/`origin_part`
   e `Inline(kind="image")` na posição correta — o mesmo contrato já usado
   no T19 (nunca usar `origin_part` como nome de arquivo — vale D5).
5. **Golden tests:** rodar a suíte nos dois modos; fixture nova por formato
   com tabela/lista/heading/imagem (golden do anydoc NÃO substitui o atual).

## Riscos

- v0.1.3, muito pré-1.0; API pode quebrar entre releases.
- Regressão de metadado é certa, não hipotética (nome de aba e slide somem).
- Vendor: projeto de empresa cujo produto principal é a API paga; o MIT
  pode não ser mantido com o mesmo empenho.
- Se T15 (pdf-inspector) e T18 forem ambos aprovados, `anydoc` sozinho
  cobre PDF+docs — avaliar adotar só ele em vez de duas dependências
  (decisão no ADR correspondente).

## Fora de escopo

T19 (unificação de imagens) — **concluído**. PDF (`--parser mupdf|inspector`)
— PR 3, separado. Streaming, compressão de asset, GUI.

## Sequência

```
PR 3 — feat/parser-inspector  (bloqueado: corpus ≥20 PDFs) — INDEPENDENTE
PR 4 — feat/parser-anydoc     (T17 → T18) — este plano
```

Regressão `pytest tests/ -v` verde antes de qualquer gate. PR para `main`
(sem push direto — branch protection já ativa, verificado hoje).
