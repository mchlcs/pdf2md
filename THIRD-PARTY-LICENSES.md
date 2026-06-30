# Licenças de Terceiros

O código-fonte do **pdf2md** é licenciado sob **MIT** (ver [LICENSE](LICENSE)).

O **binário distribuído** (`PDF2MD.app` / `.dmg`) embarca, via PyInstaller, as
bibliotecas de terceiros abaixo, cada uma sob sua própria licença. Esta página
satisfaz a atribuição exigida por essas licenças.

> ⚠️ **Importante:** o binário inclui **PyMuPDF** (e `pymupdf4llm`), licenciado
> sob **GNU AGPL-3.0** (ou licença comercial Artifex). Como AGPL é copyleft, a
> **distribuição do binário** está sujeita aos termos da AGPL para esse
> componente. O código-fonte correspondente está publicamente disponível em
> https://github.com/phant0um/pdf2md (pdf2md) e https://github.com/pymupdf/PyMuPDF
> (PyMuPDF), cumprindo a obrigação de disponibilização de fonte.

---

## Dependências embarcadas no binário

| Biblioteca | Versão | Licença | Projeto |
|---|---|---|---|
| PyMuPDF | 1.27.2.3 | **AGPL-3.0** ou Artifex Commercial | https://github.com/pymupdf/PyMuPDF |
| pymupdf4llm | 1.27.2.3 | **AGPL-3.0** ou Artifex Commercial | https://github.com/pymupdf/RAG |
| mammoth | 1.12.0 | BSD-2-Clause | https://github.com/mwilliamson/python-mammoth |
| python-docx | 1.2.0 | MIT | https://github.com/python-openxml/python-docx |
| pytesseract | 0.3.13 | Apache-2.0 | https://github.com/madmaze/pytesseract |
| Pillow | 12.2.0 | HPND (MIT-CMU) | https://github.com/python-pillow/Pillow |
| pillow-heif | 1.3.0 | BSD-3-Clause | https://github.com/bigcat88/pillow_heif |
| typer | 0.26.3 | MIT | https://github.com/fastapi/typer |
| rich | 15.0.0 | MIT | https://github.com/Textualize/rich |
| PyYAML | 6.0.3 | MIT | https://github.com/yaml/pyyaml |

## Dependências externas (NÃO embarcadas)

Chamadas via `subprocess` — executáveis separados que o usuário instala
(`brew install ...`). Isolamento por processo: não há linkagem, então suas
licenças **não** se propagam ao código do pdf2md.

| Executável | Licença | Uso |
|---|---|---|
| Tesseract OCR | Apache-2.0 | OCR de imagens e PDFs escaneados |
| antiword | GPL-2.0 | Conversão de `.doc` (Word binário OLE) |

---

## Implicações práticas

- **Usar o app:** sem restrição.
- **Redistribuir o `.dmg`:** mantenha esta atribuição e o aviso AGPL; o
  source-code correspondente deve permanecer disponível (já é público).
- **Fork / código próprio:** o código pdf2md é MIT; reutilize livremente. Se
  você distribuir um binário que embarque PyMuPDF, as obrigações AGPL se aplicam
  à sua distribuição também.
- **Quer um binário sem copyleft?** requer licença comercial Artifex para
  PyMuPDF, ou substituir a engine de PDF (inviável — é o core).

Os textos completos das licenças estão nos respectivos repositórios linkados
acima e nos metadados dos pacotes (`pip show <pacote>`).
