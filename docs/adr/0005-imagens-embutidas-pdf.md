# ADR 0005: Extração de imagens embutidas de PDF (feature `--imagens`)

## Status
Aceito

## Contexto

`pdf_to_md` chamava `pymupdf4llm.to_markdown()` sem `write_images` — toda
imagem embutida era descartada. O usuário pediu escolher entre transcrever
(OCR) ou preservar as imagens do PDF. Escopo fechado: **somente PDF**.

Decisões travadas:

| # | Decisão | Escolha | Motivo |
|---|---|---|---|
| D1 | Destino dos assets | `<stem>_assets/` ao lado do `.md`; `--obsidian` → `vault/attachments/` + `![[wikilink]]` | Obsidian não resolve `![]()` relativo de forma confiável |
| D2 | Base64 inline | **Não** | +33% no `.md`, quebra render do Obsidian, mata diff |
| D3 | Página-scan (sem texto nativo) | Em `extrair`/`ambos`, persiste o render 300 dpi como `p{n:03d}_full.png` | `get_images()` num scan devolve 1 imagem = a página inteira; persistir o render evita path duplicado |
| D4 | Dedup | SHA-256 dos bytes → 1 arquivo por hash, N links | Logo de rodapé em 200 páginas = 200 PNGs sem isso |
| D5 | Nomenclatura | `img_p{pagina:03d}_{idx}.{ext}` — **sempre gerado**, nunca derivado de metadado do PDF | Mitiga path traversal (CWE-22) |

## Decisão

1. **API:** `pdf_to_md(..., modo_imagem, assets_dir, md_dir, wikilinks,
   prefixo_nome, avisos)`; flag CLI `--imagens transcrever|extrair|ambos|ignorar`
   + `--assets-dir`. Default `transcrever` ⇒ **byte-idêntico** ao comportamento
   atual (sem assets, sem links, OCR só de scans).
2. **Modo `ambos`:** extrai + roda OCR na imagem e usa o resultado como
   alt-text do link (`![OCR](assets/...)`). Alt-text enxuto: primeira linha,
   120 chars.
3. **Modo `ignorar`:** páginas-scan ficam sem OCR e sem render persistido.
4. **Dedup e diretórios compartilhados:** assets em diretório por arquivo
   (`<stem>_assets/`) usam nomes simples; diretório COMPARTILHADO
   (`--assets-dir` explícito ou `vault/attachments`) ganha prefixo por stem
   (`<stem>__img_p001_0.png`) — sem colisão sob `ThreadPoolExecutor`.
5. **Não-PDF:** a flag é ignorada com aviso por arquivo ("--imagens só se
   aplica a PDFs"), mesma semântica de `--ignorar-margens` (só afeta PDF).
6. **Link relativo:** `os.path.relpath` entre o asset (resolvido) e o
   `md_dir` resolvido — no macOS `/var` é symlink de `/private/var` e a
   mistura de path resolvido/não-resolvido gerava relpath gigante.

## Segurança (gate Sentinel)

- **Path traversal (CWE-22):** nomes são SEMPRE gerados (D5). A extensão
  vinda do documento passa por allowlist (`_EXTENSOES_SEGURAS`); fora dela,
  normalização para PNG via `Pixmap` — revalidada na fronteira de escrita
  (defesa em profundidade). `_caminho_seguro` valida regex de nome e assert
  de containment (`assets_dir in caminho.parents`).
- **Resource bomb:** `_MAX_IMAGENS_PDF = 500` por documento (inclui scans),
  `_MAX_BYTES_IMAGEM = 50 MB` por imagem, `_MAX_BYTES_RENDER_PAGINA = 50 MB`
  por render. Excedeu → skip + aviso, nunca crash.
- **Symlink:** `assets_dir` que é symlink → recusa (`ValueError` genérico,
  sem path do usuário).
- **Erros sem path:** mensagens de aviso contêm só nome/índice — nunca
  caminhos absolutos (CWE-209). Stack traces preservam o padrão `RuntimeError`
  genérico de `converter.py`.

## Consequências

- Fixture com 2 imagens → 2 PNGs em disco + 2 links `![]()`; modo default
  não escreve nada (teste de byte-identidade).
- Avisos de extração (limites, imagens ilegíveis) aparecem no JSON/CLI/GUI
  via a lista `avisos` do resultado do batch.
- Fora de escopo (PR futuro): DOCX/PPTX/XLSX, GUI SwiftUI, conversão de
  formato (HEIC→PNG), compressão de asset, posição exata do link no fluxo
  do texto (links vão ao fim do chunk da página).

## Alternativas rejeitadas

- **Base64 inline (D2):** infla o MD e quebra Obsidian/diff.
- **Nome derivado do metadado do PDF:** superfície de ataque direta (CWE-22).
- **`write_images` do pymupdf4llm:** gera nomes dos metadados e não dá
  controle de diretório/dedup/limites — a camada própria (`core/pdf_images.py`)
  ficou sob nosso controle de segurança.

---

## Emenda — T19: unificação com DOCX (2026-08-04)

A Parte 1 afirmava que DOCX "descarta imagem, texto só" — **errado**: o
`doc_to_md()` (mammoth) embutia **data-URI base64** por padrão
(`![](data:image/png;base64,...)`). Ou seja, a política era inconsistente:
PDF descartava, DOCX embutia — e o base64, rejeitado na D2, era o padrão de
fato do DOCX.

### Decisão (T19)

1. **DOCX para de embutir base64 por padrão.** `transcrever` (default) e
   `ignorar` descartam imagens — handler vazio do mammoth
   (`mammoth.images.img_element`), que substitui o data-URI padrão.
   Mudança de comportamento intencional (D2).
2. **DOCX respeita `--imagens`:** `extrair` grava assets e insere o link no
   **ponto exato** do documento (o handler do mammoth preserva posição —
   vantagem sobre o PDF, que anexa links no fim do chunk da página); `ambos`
   extrai + OCR como alt-text.
3. **Maquinaria compartilhada:** `core/image_assets.py` (dedup D4, nome
   sempre gerado D5, limites, symlink, containment) serve PDF e DOCX.
   `core/pdf_images.py` ficou só com a parte PyMuPDF. Nomes do DOCX:
   `img_{n:04d}.{ext}`; content-type fora do mapa de MIME → descartada com
   aviso (ex.: EMF não tem conversor confiável).
4. **Wikilinks (D1):** pós-processamento seguro — só links cujo `src` é um
   nome gerado por nós viram `![[...]]`.
5. **Aviso de formato:** só PPTX/XLSX/CSV/imagem recebem o aviso
   "--imagens só se aplica a PDF e DOCX".
